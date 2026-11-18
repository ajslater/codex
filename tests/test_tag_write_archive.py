"""
What a real CBZ tag write leaves in the archive under comicbox 5.6.2.

- A free-text zip comment survives the write (5.6.1 cleared it).
- An archive whose tag file precedes its pages is copied to a hidden
  ``.<name>.comicbox.tmp`` beside it and swapped in. Afterwards the
  formats codex did not name are gone, as before, and no temp file is
  left in the library.
- Under ``keep`` the formats codex did not name are rewritten with the new
  tags instead, a comicbox.yaml among them (never added), and a comic
  whose tag file does not parse is refused and listed as a tag-write error.
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
from codex.librarian.scribe.tagwrite_errors import (
    clear_tag_write_errors,
    get_tag_write_errors,
)
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from tests.tmp_dirs import tmp_dir

_TMP_DIR: Final = tmp_dir("codex.tests.tagwritearchive")
_EXAMPLE_CBZ: Final = Path(__file__).parent / "files" / "comicbox-2-example.cbz"
_COMMENT: Final = b"Scanned by a person, not a tagger."
_PAGE: Final = b"\xff\xd8\xff\xe0not-a-real-jpeg"
_COMIC_INFO: Final = (
    b'<?xml version="1.0" encoding="utf-8"?>\n'
    b"<ComicInfo><Series>Kept</Series><Number>1</Number></ComicInfo>"
)
_METRON_INFO: Final = (
    b'<?xml version="1.0" encoding="utf-8"?>\n'
    b"<MetronInfo><Series><Name>Kept</Name></Series><Number>1</Number></MetronInfo>"
)
_UNPARSABLE_METRON_INFO: Final = b'<?xml version="1.0"?>\n<MetronInfo><Series>'
_KEEP: Final = ("COMIC_INFO", "keep")


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
        clear_tag_write_errors()
        self.addCleanup(clear_tag_write_errors)

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

    def _tagged_comic(self, name: str, metron_info: bytes) -> Comic:
        """Make a CBZ comic carrying ComicInfo.xml and MetronInfo.xml."""
        path = _TMP_DIR / name
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("page1.jpg", _PAGE)
            zf.writestr("ComicInfo.xml", _COMIC_INFO)
            zf.writestr("MetronInfo.xml", metron_info)
        return self._comic(path)

    @staticmethod
    def _write(comic: Comic, formats: tuple[str, ...] = ("COMIC_INFO",)) -> None:
        task = BulkTagWriteTask(
            comic_pks=frozenset({comic.pk}),
            patch={"title": "Written"},
            mode="update",
            formats=formats,
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

    def test_without_keep_an_unnamed_format_is_removed(self) -> None:
        comic = self._tagged_comic("dropped.cbz", _METRON_INFO)

        self._write(comic)

        with zipfile.ZipFile(comic.path) as zf:
            names = zf.namelist()
        assert "ComicInfo.xml" in names
        assert "MetronInfo.xml" not in names

    def test_keep_rewrites_an_unnamed_format(self) -> None:
        comic = self._tagged_comic("kept.cbz", _METRON_INFO)

        self._write(comic, _KEEP)

        with zipfile.ZipFile(comic.path) as zf:
            names = zf.namelist()
            metron_info = zf.read("MetronInfo.xml").decode()
        assert "ComicInfo.xml" in names
        # Kept and rewritten with the new tags: the title is a MetronInfo story.
        assert "<Name>Kept</Name>" in metron_info
        assert "<Story>Written</Story>" in metron_info
        assert not {"comicbox.yaml", "comicbox.json"} & set(names), names
        assert not get_tag_write_errors()

    def test_keep_rewrites_a_carried_comicbox_yaml(self) -> None:
        path = _TMP_DIR / "example.cbz"
        shutil.copy(_EXAMPLE_CBZ, path)
        comic = self._comic(path)

        self._write(comic, _KEEP)

        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            comicbox_yaml = zf.read("comicbox.yaml").decode()
        assert "ComicInfo.xml" in names
        assert "Written" in comicbox_yaml

    def test_keep_refuses_a_comic_with_an_unparsable_tag_file(self) -> None:
        comic = self._tagged_comic("broken.cbz", _UNPARSABLE_METRON_INFO)

        self._write(comic, _KEEP)

        errors = [e for e in get_tag_write_errors() if e["path"] == str(comic.path)]
        assert len(errors) == 1, errors
        assert "could not be parsed" in errors[0]["error"]
        with zipfile.ZipFile(comic.path) as zf:
            # Refused before anything was written: the comic is as it was.
            assert zf.read("MetronInfo.xml") == _UNPARSABLE_METRON_INFO
            assert zf.read("ComicInfo.xml") == _COMIC_INFO
