"""
The tag-write endpoints accept only the write formats the editors offer.

``formats`` was a list of any strings passed straight to comicbox. comicbox
5.6.2 makes ``PDF`` rewrite a PDF's document metadata; the UI never sends
it, so the API refuses it. comicbox's ``keep`` (also rewrite the tag formats
a comic already carries instead of removing them) is offered, but only
beside a named format: alone it names nothing, and comicbox skips an
untagged comic without a word.
"""

import json
import shutil
from http import HTTPStatus
from typing import Final, override
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_TMP_DIR: Final = tmp_dir("codex.tests.tagwrite_formats")
_URLS: Final = ("/api/v4/admin/tag-write", "/api/v4/admin/tag-write/preflight")


class TagWriteFormatsTestCase(TestCase):
    """Unknown write formats are a 400 on the write and the preflight."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        path = _TMP_DIR / "c.cbz"
        path.touch()
        self.comic = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library,
            path=path,
            issue_number=1,
            name="c",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
            file_type="CBZ",
        )
        admin = User.objects.create_user(
            username="formats_admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _post(self, url: str, formats: list[str]):
        payload = {
            "collection": "comics",
            "pks": [str(self.comic.pk)],
            "patch": json.dumps({"title": "t"}),
            "mode": "update",
            "formats": formats,
        }
        with patch("codex.views.admin.tagwrite.LIBRARIAN_QUEUE") as queue:
            resp = self.client.post(
                url, data=json.dumps(payload), content_type="application/json"
            )
        return resp, queue

    def test_unknown_formats_are_refused(self) -> None:
        """``PDF`` and ``COMICBOX_YAML`` never reach comicbox."""
        for url in _URLS:
            for fmt in ("PDF", "COMICBOX_YAML"):
                with self.subTest(url=url, fmt=fmt):
                    resp, queue = self._post(url, ["COMIC_INFO", fmt])
                    assert resp.status_code == HTTPStatus.BAD_REQUEST, resp.content
                    assert not queue.put.called

    def test_empty_formats_are_refused(self) -> None:
        """Comicbox refuses a write with no formats; say so up front."""
        for url in _URLS:
            with self.subTest(url=url):
                resp, _ = self._post(url, [])
                assert resp.status_code == HTTPStatus.BAD_REQUEST, resp.content

    def test_keep_alone_is_refused(self) -> None:
        """``keep`` needs a named format to keep the others beside."""
        for url in _URLS:
            with self.subTest(url=url):
                resp, queue = self._post(url, ["keep"])
                assert resp.status_code == HTTPStatus.BAD_REQUEST, resp.content
                assert not queue.put.called

    def test_keep_with_a_named_format_is_queued(self) -> None:
        """``keep`` beside a named format reaches comicbox, in order."""
        resp, queue = self._post(_URLS[0], ["COMIC_INFO", "keep"])
        assert resp.status_code == HTTPStatus.ACCEPTED, resp.content
        assert queue.put.call_args.args[0].formats == ("COMIC_INFO", "keep")

        resp, _ = self._post(_URLS[1], ["keep", "METRON_INFO"])
        assert resp.status_code == HTTPStatus.OK, resp.content

    def test_known_formats_are_queued_once_each(self) -> None:
        """The editors' formats pass, deduplicated, in order."""
        resp, queue = self._post(_URLS[0], ["METRON_INFO", "COMIC_INFO", "METRON_INFO"])
        assert resp.status_code == HTTPStatus.ACCEPTED, resp.content
        assert queue.put.call_args.args[0].formats == ("METRON_INFO", "COMIC_INFO")


@pytest.mark.parametrize("fmt", ["COMIC_INFO", "METRON_INFO", "keep"])
def test_write_formats_are_the_editor_formats(fmt: str) -> None:
    """Guard the allow-list the endpoint validates against."""
    from codex.choices.tagging import WRITE_FORMATS

    assert fmt in WRITE_FORMATS
    assert "PDF" not in WRITE_FORMATS
