"""
comicbox 5.7's ``keep`` write keyword, as codex sends it.

A write that names one tag format deletes the comic's others unless the
formats also hold ``keep``. The admin default and the per-write override
decide whether codex adds it.
"""

import io
import shutil
import zipfile
from http import HTTPStatus
from typing import Any, Final, override
from unittest.mock import patch

from comicbox.box import Comicbox
from comicbox.write import BulkWriteItem, bulk_write
from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import Client, SimpleTestCase, TestCase
from PIL import Image

from codex.choices.tagging import KEEP_FORMATS, write_formats
from codex.models import ComicboxTaggingDefaults
from codex.views.admin.tagwrite import AdminTagWriteView
from tests.tmp_dirs import tmp_dir

_TMP_DIR: Final = tmp_dir("codex.tests.tagwritekeep")
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_PK: Final = 7
_TAG_WRITE_URL: Final = "/api/v4/admin/tag-write"
_QUEUE_TARGET: Final = "codex.views.admin.tagwrite.LIBRARIAN_QUEUE"


class WriteFormatsTests(SimpleTestCase):
    """``write_formats`` appends the keyword only when asked."""

    def test_keep(self) -> None:
        """Keep adds the keyword after the named formats."""
        assert write_formats(["COMIC_INFO"], keep=True) == ("COMIC_INFO", KEEP_FORMATS)

    def test_no_keep(self) -> None:
        """Without keep the formats pass through."""
        assert write_formats(["COMIC_INFO"], keep=False) == ("COMIC_INFO",)


class TagWriteKeepViewTests(TestCase):
    """The tag-write view resolves keep from the request or the admin default."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        self.client = Client()
        admin = User.objects.create_user(
            username="keep_admin",
            password=_TEST_PASSWORD,
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(admin)

    def _formats(self, body: dict[str, Any]) -> tuple[str, ...]:
        with (
            patch.object(
                AdminTagWriteView, "resolve_comic_pks", return_value=frozenset({_PK})
            ),
            patch(_QUEUE_TARGET) as mocked_queue,
        ):
            response = self.client.post(
                _TAG_WRITE_URL,
                data={"collection": "comics", "pks": [str(_PK)], "patch": "{}", **body},
                content_type="application/json",
            )
        assert response.status_code == HTTPStatus.ACCEPTED
        return mocked_queue.put.call_args.args[0].formats

    def test_default_off(self) -> None:
        """No default and no request value writes only the named formats."""
        assert self._formats({"formats": ["COMIC_INFO"]}) == ("COMIC_INFO",)

    def test_default_on(self) -> None:
        """The admin default adds keep."""
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"keep_formats": True}
        )
        assert self._formats({"formats": ["COMIC_INFO"]}) == (
            "COMIC_INFO",
            KEEP_FORMATS,
        )

    def test_request_overrides_default(self) -> None:
        """A request's own value wins over the default."""
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"keep_formats": True}
        )
        formats = self._formats({"formats": ["COMIC_INFO"], "keepFormats": False})
        assert formats == ("COMIC_INFO",)


class KeepFormatsWriteTests(SimpleTestCase):
    """comicbox keeps the other tag file when codex's formats hold keep."""

    @override
    def setUp(self) -> None:
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.path = _TMP_DIR / "keep.cbz"  # pyright: ignore[reportUninitializedInstanceVariable]
        buf = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buf, "JPEG")
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr("001.jpg", buf.getvalue())
        self._write({"series": {"name": "S"}}, ("COMIC_INFO", "METRON_INFO"))

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _write(self, patch_: dict, formats: tuple[str, ...]) -> None:
        item = BulkWriteItem(
            path=self.path,
            patch=patch_,
            merge_mode="update",
            formats=frozenset(formats),
        )
        for result in bulk_write([item]):
            assert not result.error, result.error

    def _tag_files(self) -> set[str]:
        with zipfile.ZipFile(self.path) as archive:
            return {name for name in archive.namelist() if name.endswith(".xml")}

    def test_keep_keeps_metron_info(self) -> None:
        """Writing ComicInfo with keep leaves MetronInfo in place."""
        self._write({"title": "T"}, write_formats(["COMIC_INFO"], keep=True))
        assert self._tag_files() == {"ComicInfo.xml", "MetronInfo.xml"}
        with Comicbox(self.path) as cb:
            assert cb.to_dict()["comicbox"]["title"] == "T"

    def test_no_keep_removes_metron_info(self) -> None:
        """Without keep, the format not named goes."""
        self._write({"title": "T"}, write_formats(["COMIC_INFO"], keep=False))
        assert self._tag_files() == {"ComicInfo.xml"}
