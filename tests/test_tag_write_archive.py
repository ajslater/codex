"""
What a real CBZ tag write leaves in the archive under comicbox 5.6.2.

- A free-text zip comment survives the write (5.6.1 cleared it).
- An archive whose tag file precedes its pages is copied to a hidden
  ``.<name>.comicbox.tmp`` beside it and swapped in. Afterwards the
  formats codex did not name are gone, as before, and no temp file is
  left in the library.
"""

import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any, Final, override
from unittest.mock import MagicMock

from django.test import TestCase
from loguru import logger

from codex.librarian.scribe.tag_writer import TagWriter
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from tests.tmp_dirs import tmp_dir

_TMP_DIR: Final = tmp_dir("codex.tests.tagwritearchive")
_EXAMPLE_CBZ: Final = Path(__file__).parent / "files" / "comicbox-2-example.cbz"
_COMMENT: Final = b"Scanned by a person, not a tagger."
_PAGE: Final = b"\xff\xd8\xff\xe0not-a-real-jpeg"


def _double(stub: object) -> Any:
    """Pass a test double through a concretely-typed seam."""
    return stub


def _make_writer() -> TagWriter:
    """Build a TagWriter without the threading machinery."""
    writer = TagWriter.__new__(TagWriter)
    writer.log = _double(logger)
    writer.librarian_queue = _double(MagicMock())
    writer.status_controller = _double(MagicMock())
    writer.abort_event = threading.Event()
    return writer


class TagWriteArchiveTestCase(TestCase):
    """A COMIC_INFO write to a CBZ on disk."""

    @override
    def setUp(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, _TMP_DIR, ignore_errors=True)
        self.library = Library.objects.create(path=str(_TMP_DIR), events=False)  # pyright: ignore[reportUninitializedInstanceVariable]
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        self.volume = Volume.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="1", publisher=publisher, imprint=imprint, series=series
        )

    def _comic(self, path: Path) -> Comic:
        volume = self.volume
        return Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=1,
            name="c",
            publisher=volume.publisher,
            imprint=volume.imprint,
            series=volume.series,
            volume=volume,
            size=path.stat().st_size,
            file_type="CBZ",
        )

    @staticmethod
    def _write(comic: Comic) -> None:
        task = BulkTagWriteTask(
            comic_pks=frozenset({comic.pk}),
            patch={"title": "Written"},
            mode="update",
            formats=("COMIC_INFO",),
            delete_original=False,
            rename=False,
        )
        _make_writer().write_tags(task)

    def test_a_free_text_zip_comment_survives(self) -> None:
        path = _TMP_DIR / "commented.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.comment = _COMMENT
            zf.writestr("page1.jpg", _PAGE)
        comic = self._comic(path)

        self._write(comic)

        with zipfile.ZipFile(path) as zf:
            assert "ComicInfo.xml" in zf.namelist()
            assert zf.comment == _COMMENT

    def test_the_copy_path_leaves_no_temp_file_and_no_other_formats(self) -> None:
        path = _TMP_DIR / "example.cbz"
        shutil.copy(_EXAMPLE_CBZ, path)
        with zipfile.ZipFile(path) as zf:
            # The tag file precedes the page, which is what takes the copy.
            assert zf.namelist()[0] == "comicbox.yaml"
        comic = self._comic(path)

        self._write(comic)

        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        assert "ComicInfo.xml" in names
        assert "comicbox.yaml" not in names
        leftovers = [p.name for p in _TMP_DIR.iterdir() if p.name.startswith(".")]
        assert not leftovers, leftovers
