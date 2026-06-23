"""
Read-only libraries are never written to.

A library marked ``read_only`` must be excluded from every tag-write / online-tag
resolution, and a selection that lands entirely in read-only libraries must hide
the edit entry points (``editable`` is false in the metadata payload). Mixed
selections write only the editable comics and report how many were skipped.
"""

import json
import shutil
from http import HTTPStatus
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_TMP_DIR: Final = Path("/tmp/codex.tests.readonly")  # noqa: S108
_RW_DIR: Final = _TMP_DIR / "rw"
_RO_DIR: Final = _TMP_DIR / "ro"
_TAG_WRITE_URL: Final = "/api/v4/admin/tag-write"
_PREFLIGHT_URL: Final = "/api/v4/admin/tag-write/preflight"
_ONLINE_TAG_URL: Final = "/api/v4/admin/tag-sessions/start"


class ReadOnlyLibraryTestCase(TestCase):
    """A read-only library is never resolved as a write target."""

    @override
    def setUp(self) -> None:
        """Seed one writable and one read-only library under a shared publisher."""
        cache.clear()
        init_admin_flags()
        _RW_DIR.mkdir(exist_ok=True, parents=True)
        _RO_DIR.mkdir(exist_ok=True, parents=True)

        rw_library = Library.objects.create(path=str(_RW_DIR))
        ro_library = Library.objects.create(path=str(_RO_DIR), read_only=True)
        publisher = Publisher.objects.create(name="Image")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        self.rw_comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            rw_library, publisher, imprint, series, volume, _RW_DIR, "rw"
        )
        self.ro_comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            ro_library, publisher, imprint, series, volume, _RO_DIR, "ro"
        )
        self.publisher_pk = publisher.pk  # pyright: ignore[reportUninitializedInstanceVariable]

        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="readonly_admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.admin)

    @staticmethod
    def _make_comic(library, publisher, imprint, series, volume, dir_path, name):
        path = dir_path / f"{name}.cbz"
        path.touch()
        return Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name=name,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
            file_type="CBZ",
        )

    @override
    def tearDown(self) -> None:
        """Remove the touch files."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _post(self, url: str, payload: dict):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )

    @staticmethod
    def _body(response):
        """Unwrap the v4 ``{data, meta, errors}`` envelope when present."""
        body = response.json()
        if isinstance(body, dict) and "data" in body and "meta" in body:
            return body["data"]
        return body

    def _write_payload(self, collection: str, pks) -> dict:
        return {
            "collection": collection,
            "pks": [str(pk) for pk in pks],
            "patch": json.dumps({"publisher": "Image"}),
            "mode": "update",
            "formats": ["COMIC_INFO"],
        }

    def test_tag_write_skips_read_only(self) -> None:
        """A publisher write spanning both libraries touches only the writable comic."""
        payload = self._write_payload("publishers", [self.publisher_pk])
        with patch("codex.views.admin.tagwrite.LIBRARIAN_QUEUE") as queue:
            resp = self._post(_TAG_WRITE_URL, payload)
        assert resp.status_code == HTTPStatus.ACCEPTED, resp.content
        task = queue.put.call_args.args[0]
        assert frozenset(task.comic_pks) == {self.rw_comic.pk}
        assert self._body(resp)["skipped"] == 1

    def test_tag_write_all_read_only_is_rejected(self) -> None:
        """Selecting only the read-only comic resolves to nothing -> 400."""
        payload = self._write_payload("comics", [self.ro_comic.pk])
        with patch("codex.views.admin.tagwrite.LIBRARIAN_QUEUE") as queue:
            resp = self._post(_TAG_WRITE_URL, payload)
        assert resp.status_code == HTTPStatus.BAD_REQUEST, resp.content
        assert not queue.put.called

    def test_preflight_reports_skipped(self) -> None:
        """Preflight reports the editable total and the read-only skip count."""
        payload = self._write_payload("publishers", [self.publisher_pk])
        resp = self._post(_PREFLIGHT_URL, payload)
        assert resp.status_code == HTTPStatus.OK, resp.content
        data = self._body(resp)
        assert data["total"] == 1
        assert data["skipped"] == 1

    def test_online_tag_skips_read_only(self) -> None:
        """An online-tag scan over the publisher excludes the read-only comic."""
        payload = {"collection": "publishers", "pks": [str(self.publisher_pk)]}
        with patch("codex.views.admin.onlinetag.LIBRARIAN_QUEUE") as queue:
            resp = self._post(_ONLINE_TAG_URL, payload)
        assert resp.status_code == HTTPStatus.ACCEPTED, resp.content
        task = queue.put.call_args.args[0]
        assert frozenset(task.comic_pks) == {self.rw_comic.pk}
        assert self._body(resp)["skipped"] == 1

    def _editable(self, collection: str, pks) -> bool:
        pks_str = ",".join(str(pk) for pk in pks)
        url = f"/api/v4/browse/{collection}/{pks_str}/metadata"
        resp = self.client.get(url)
        assert resp.status_code == HTTPStatus.OK, resp.content
        return self._body(resp)["editable"]

    def test_metadata_editable_writable_comic(self) -> None:
        """A writable comic is editable."""
        assert self._editable("comics", [self.rw_comic.pk]) is True

    def test_metadata_editable_read_only_comic(self) -> None:
        """A read-only comic is not editable -> buttons hidden."""
        assert self._editable("comics", [self.ro_comic.pk]) is False

    def test_metadata_editable_mixed_selection(self) -> None:
        """A publisher spanning both libraries stays editable (one writable comic)."""
        assert self._editable("publishers", [self.publisher_pk]) is True
