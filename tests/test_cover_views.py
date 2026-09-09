"""
Conditional-GET behaviour of the per-pk cover endpoints.

These routes used to carry ``cache_page``, which stored a copy of every
cover response body in the default cache — one per user, because the
page-cache key hashes the ``Vary`` header values — and could only be
invalidated by clearing that whole cache. They now serve ``ETag`` /
``Last-Modified`` derived from the thumb's size and mtime instead, so a
regenerated cover invalidates itself and a broad ``cache.clear()`` can no
longer evict a cover.
"""

from __future__ import annotations

import os
import shutil
from base64 import b64encode
from http import HTTPStatus
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache, caches
from django.test import Client, TestCase

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.tasks import CoverCreateTask
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.auth import GroupAuth
from codex.startup import init_admin_flags
from codex.urls.const import COVER_MAX_AGE

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_TMP_DIR: Final = Path("/tmp/codex.tests.covers")  # noqa: S108
_OPEN_DIR: Final = _TMP_DIR / "open"
_PRIVATE_DIR: Final = _TMP_DIR / "private"
_COVERS_ROOT: Final = _TMP_DIR / "covers"
_CUSTOM_COVERS_ROOT: Final = _TMP_DIR / "custom-covers"
# Not a real WEBP — nothing in the serving path decodes it.
_COVER_BYTES: Final = b"RIFF\x00\x00\x00\x00WEBPfake-cover-bytes"
_QUEUE_PATCH: Final = "codex.views.browser.cover.LIBRARIAN_QUEUE"


class CoverViewTestCase(TestCase):
    """Cover the per-pk cover endpoints end to end."""

    @override
    def setUp(self) -> None:
        """Seed a visible comic, an ACL-restricted comic, and a cover root."""
        cache.clear()
        init_admin_flags()
        for path in (_OPEN_DIR, _PRIVATE_DIR, _COVERS_ROOT, _CUSTOM_COVERS_ROOT):
            path.mkdir(exist_ok=True, parents=True)

        # The cover roots are class attributes resolved at import time from
        # ROOT_CACHE_PATH, so redirect them rather than the settings they came
        # from — otherwise these tests would write into the real config dir.
        for attr, root in (
            ("COVERS_ROOT", _COVERS_ROOT),
            ("CUSTOM_COVERS_ROOT", _CUSTOM_COVERS_ROOT),
        ):
            patcher = patch.object(CoverPathMixin, attr, root)
            patcher.start()
            self.addCleanup(patcher.stop)

        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        self.groups = (publisher, imprint, series, volume)  # pyright: ignore[reportUninitializedInstanceVariable]

        # An ungrouped library is visible to everyone.
        self.comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            Library.objects.create(path=str(_OPEN_DIR)), _OPEN_DIR, "open"
        )
        # A library behind a group the test user does not belong to.
        private_library = Library.objects.create(path=str(_PRIVATE_DIR))
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        private_library.groups.add(readers)
        self.private_comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            private_library, _PRIVATE_DIR, "private"
        )

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="cover-reader", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

        self.cover_path = CoverPathMixin.get_cover_path(self.comic.pk, custom=False)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.url = f"/api/v4/comics/{self.comic.pk}/cover"  # pyright: ignore[reportUninitializedInstanceVariable]
        self.dispatch_url = f"/api/v4/covers/comic/{self.comic.pk}"  # pyright: ignore[reportUninitializedInstanceVariable]
        self.opds_url = f"/opds/bin/c/{self.comic.pk}/cover.webp"  # pyright: ignore[reportUninitializedInstanceVariable]

    def _make_comic(self, library, dir_path: Path, name: str) -> Comic:
        """Create a Comic row backed by a touch file."""
        path = dir_path / f"{name}.cbz"
        path.touch()
        publisher, imprint, series, volume = self.groups
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

    def _write_cover(self, data: bytes = _COVER_BYTES) -> None:
        """Write a thumb where the view expects to find it."""
        self.cover_path.parent.mkdir(exist_ok=True, parents=True)
        self.cover_path.write_bytes(data)

    @override
    def tearDown(self) -> None:
        """Drop the touch files and the redirected cover roots."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_present_cover_carries_validators(self) -> None:
        """A served cover advertises how to revalidate it and for how long."""
        self._write_cover()

        response = self.client.get(self.url)

        assert response.status_code == HTTPStatus.OK
        assert response.content == _COVER_BYTES
        assert response.headers["ETag"]
        assert response.headers["Last-Modified"]
        # ACL-gated, so a shared proxy must not store it.
        assert response.headers["Cache-Control"] == f"private, max-age={COVER_MAX_AGE}"

    def test_matching_etag_is_not_modified(self) -> None:
        """A revalidating client gets a bodiless 304 and keeps its copy."""
        self._write_cover()
        etag = self.client.get(self.url).headers["ETag"]

        response = self.client.get(self.url, headers={"if-none-match": etag})

        assert response.status_code == HTTPStatus.NOT_MODIFIED
        assert not response.content
        # RFC 9110 §15.4.5 — a 304 repeats the validators and freshness.
        assert response.headers["ETag"] == etag
        assert response.headers["Cache-Control"] == f"private, max-age={COVER_MAX_AGE}"

    def test_not_modified_is_answered_from_the_stat_alone(self) -> None:
        """The 304 path never reads the image bytes."""
        self._write_cover()
        etag = self.client.get(self.url).headers["ETag"]

        # Swap in different bytes of the same length and restore the mtime, so
        # the validators are untouched but the body is not what was served.
        stat = self.cover_path.stat()
        self.cover_path.write_bytes(b"X" * stat.st_size)
        os.utime(self.cover_path, ns=(stat.st_atime_ns, stat.st_mtime_ns))

        response = self.client.get(self.url, headers={"if-none-match": etag})

        assert response.status_code == HTTPStatus.NOT_MODIFIED
        assert not response.content

    def test_regenerated_cover_invalidates_its_etag(self) -> None:
        """A rewritten thumb answers a stale validator with the new bytes."""
        self._write_cover()
        etag = self.client.get(self.url).headers["ETag"]

        new_bytes = _COVER_BYTES + b"-regenerated"
        self._write_cover(new_bytes)

        response = self.client.get(self.url, headers={"if-none-match": etag})

        assert response.status_code == HTTPStatus.OK
        assert response.content == new_bytes
        assert response.headers["ETag"] != etag

    def test_if_modified_since_is_honored(self) -> None:
        """OPDS clients that only speak dates revalidate too."""
        self._write_cover()
        last_modified = self.client.get(self.url).headers["Last-Modified"]

        response = self.client.get(
            self.url, headers={"if-modified-since": last_modified}
        )

        assert response.status_code == HTTPStatus.NOT_MODIFIED

    def test_cover_survives_a_default_cache_clear(self) -> None:
        """
        The regression this endpoint's design exists to prevent.

        Import finish, tag writes, and Library / Group CRUD all call
        ``cache.clear()``. Covers must not be collateral.
        """
        self._write_cover()
        etag = self.client.get(self.url).headers["ETag"]

        caches["default"].clear()

        response = self.client.get(self.url, headers={"if-none-match": etag})
        assert response.status_code == HTTPStatus.NOT_MODIFIED

    def test_failed_cover_is_not_cacheable(self) -> None:
        """A zero-byte marker means the cover thread already gave up."""
        self._write_cover(b"")

        response = self.client.get(self.url)

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.headers["Cache-Control"] == "no-store"
        assert "ETag" not in response.headers

    @patch(_QUEUE_PATCH)
    def test_missing_cover_enqueues_and_accepts(self, mock_queue) -> None:
        """A cold cover is deferred to the cover thread, not rendered inline."""
        response = self.client.get(self.url)

        assert response.status_code == HTTPStatus.ACCEPTED
        assert response.headers["Retry-After"]
        assert response.headers["Cache-Control"] == "no-store"
        assert "ETag" not in response.headers
        enqueued = [call.args[0] for call in mock_queue.put.call_args_list]
        assert any(
            isinstance(task, CoverCreateTask) and task.pks == (self.comic.pk,)
            for task in enqueued
        )

    def test_acl_denied_cover_is_not_found(self) -> None:
        """A comic in a library the user can't see is indistinguishable from absent."""
        cover_path = CoverPathMixin.get_cover_path(self.private_comic.pk, custom=False)
        cover_path.parent.mkdir(exist_ok=True, parents=True)
        cover_path.write_bytes(_COVER_BYTES)

        response = self.client.get(f"/api/v4/comics/{self.private_comic.pk}/cover")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert not response.content

    def test_dispatch_route_carries_validators(self) -> None:
        """The route the web client actually uses gets the same treatment."""
        self._write_cover()

        response = self.client.get(self.dispatch_url)

        assert response.status_code == HTTPStatus.OK
        assert response.headers["ETag"]
        assert response.headers["Cache-Control"] == f"private, max-age={COVER_MAX_AGE}"
        # Per-user caching correctness for any downstream proxy.
        assert "Cookie" in response.headers["Vary"]

    def test_opds_cover_revalidates_under_basic_auth(self) -> None:
        """OPDS serves the same validators to a Basic-auth client."""
        self._write_cover()
        credentials = b64encode(f"cover-reader:{_TEST_PASSWORD}".encode()).decode()
        auth = {"authorization": f"Basic {credentials}"}
        client = Client()

        response = client.get(self.opds_url, headers=auth)
        assert response.status_code == HTTPStatus.OK
        etag = response.headers["ETag"]

        response = client.get(self.opds_url, headers={**auth, "if-none-match": etag})
        assert response.status_code == HTTPStatus.NOT_MODIFIED
