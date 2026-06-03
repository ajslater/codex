"""
Tag writes must honor the user's active browser filters.

Regression for a bug where writing a tag to a selected collection resolved to
*every* comic in the collection, ignoring the active file_type / read-unread
filters — e.g. a CBR-filtered publisher write leaking onto an unread CBZ.
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
from codex.models.bookmark import Bookmark
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_TMP_DIR: Final = Path("/tmp/codex.tests.tagwrite")  # noqa: S108
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"
_TAG_WRITE_URL: Final = "/api/v4/admin/tag-write"


class TagWriteFilterTestCase(TestCase):
    """A tag write only touches the comics the active filters select."""

    @override
    def setUp(self) -> None:
        """Seed a publisher with one CBR and one CBZ comic + an admin client."""
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(exist_ok=True, parents=True)

        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="Image")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        self.cbr = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            library, publisher, imprint, series, volume, "cbr", "CBR"
        )
        self.cbz = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            library, publisher, imprint, series, volume, "cbz", "CBZ"
        )
        self.publisher_pk = publisher.pk  # pyright: ignore[reportUninitializedInstanceVariable]

        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="tagwrite_admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.admin)

    @staticmethod
    def _make_comic(library, publisher, imprint, series, volume, name, file_type):
        path = _TMP_DIR / f"{name}.{file_type.lower()}"
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
            file_type=file_type,
        )

    @override
    def tearDown(self) -> None:
        """Remove the touch files."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _set_filters(self, filters: dict) -> None:
        resp = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"filters": filters}),
            content_type="application/json",
        )
        assert resp.status_code == HTTPStatus.OK, resp.content

    def _write_tags(self) -> frozenset[int]:
        """POST a publisher tag write and return the enqueued task's comic_pks."""
        payload = {
            "collection": "publishers",
            "pks": [str(self.publisher_pk)],
            "patch": json.dumps({"publisher": "Image"}),
            "mode": "update",
            "formats": ["COMIC_INFO"],
        }
        with patch("codex.views.admin.tagwrite.LIBRARIAN_QUEUE") as queue:
            resp = self.client.post(
                _TAG_WRITE_URL,
                data=json.dumps(payload),
                content_type="application/json",
            )
            assert resp.status_code == HTTPStatus.ACCEPTED, resp.content
            assert queue.put.called, "no tag write task was enqueued"
            task = queue.put.call_args.args[0]
        return frozenset(task.comic_pks)

    def test_no_filter_writes_all(self) -> None:
        """Control: with no active filter, every comic in the collection is written."""
        assert self._write_tags() == {self.cbr.pk, self.cbz.pk}

    def test_file_type_filter_excludes_unselected(self) -> None:
        """The reported bug: a CBR file_type filter must not write to the CBZ."""
        self._set_filters({"fileType": ["CBR"]})
        assert self._write_tags() == {self.cbr.pk}

    def test_read_filter_excludes_unread(self) -> None:
        """A read/unread filter is honored: READ keeps only the finished comic."""
        Bookmark.objects.create(user=self.admin, comic=self.cbr, finished=True)
        self._set_filters({"bookmark": "READ"})
        assert self._write_tags() == {self.cbr.pk}

    def test_unread_filter_excludes_read(self) -> None:
        """The inverse: UNREAD drops the finished comic, keeps the rest."""
        Bookmark.objects.create(user=self.admin, comic=self.cbr, finished=True)
        self._set_filters({"bookmark": "UNREAD"})
        assert self._write_tags() == {self.cbz.pk}
