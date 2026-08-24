"""
The tag editor's composite keys must survive a write intact.

The publish date, the alternative issue and the collection title reach
comicbox as nested patch values the tag editor assembles itself.

``test_partial_date_replaces_the_whole_date`` is the load-bearing one: the
editor sends every surviving part of a composite key on any change because an
update-mode merge replaces a top-level key wholesale rather than merging into
it. A comicbox upgrade that switched to a deep merge would silently turn the
editor's partial clears into no-ops, and that test fails here instead. The
rest cover that each new editor field reaches the archive under the comicbox
key the editor names, and that sibling top-level keys survive each other.
"""

from __future__ import annotations

import shutil
import threading
import zipfile
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, override
from unittest.mock import MagicMock

from comicbox.box import Comicbox
from django.core.cache import cache
from django.test import TestCase
from loguru import logger

from codex.choices.tagging import FORMAT_FIELD_SUPPORT
from codex.librarian.scribe.tag_writer import TagWriter
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume

_TMP_DIR: Final = Path("/tmp/codex.tests.tagwritedate")  # noqa: S108
_EXAMPLE_CBZ: Final = Path(__file__).parent / "files" / "comicbox-2-example.cbz"
_DATE: Final = MappingProxyType({"year": 1998, "month": 5, "day": 7})
_LATER_YEAR: Final = 1999
_ISSUE_NUMBER: Final = "1"
_ALTERNATIVE_ISSUE: Final = MappingProxyType({"number": 5, "suffix": "AU"})
_COLLECTION_TITLE: Final = "The Dark Phoenix Saga"


def _double(stub: object) -> Any:
    """Pass a test double through a concretely-typed seam."""
    return stub


def _make_comic(path: Path) -> Comic:
    library = Library.objects.create(path=str(_TMP_DIR), events=False)
    publisher = Publisher.objects.create(name="P")
    imprint = Imprint.objects.create(name="I", publisher=publisher)
    series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
    volume = Volume.objects.create(
        name="1", publisher=publisher, imprint=imprint, series=series
    )
    return Comic.objects.create(
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


def _make_writer() -> TagWriter:
    """Build a TagWriter without the threading machinery."""
    writer = TagWriter.__new__(TagWriter)
    writer.log = _double(logger)
    writer.librarian_queue = _double(MagicMock())
    writer.status_controller = _double(MagicMock())
    writer.abort_event = threading.Event()
    return writer


def _read_sub_md(path: Path) -> dict:
    with Comicbox(path) as cb:
        return dict(cb.get_internal_metadata().get("comicbox", {}))


def _untagged_cbz(path: Path) -> Path:
    """Build a minimal archive carrying no metadata of its own."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("page1.jpg", b"\xff\xd8\xff\xe0not-a-real-jpeg")
    return path


class TagEditorFieldSupportTestCase(TestCase):
    """The editor's field map offers every field the editor renders."""

    def test_date_parts_supported_by_both_formats(self) -> None:
        for fmt in ("COMIC_INFO", "METRON_INFO"):
            fields = set(FORMAT_FIELD_SUPPORT[fmt])
            assert {"year", "month", "day"} <= fields, fmt

    def test_format_exclusive_fields(self) -> None:
        comic_info = set(FORMAT_FIELD_SUPPORT["COMIC_INFO"])
        metron = set(FORMAT_FIELD_SUPPORT["METRON_INFO"])
        metron_only = {
            "collection_title",
            "alternative_issue_number",
            "alternative_issue_suffix",
        }
        assert metron_only <= metron
        assert not (metron_only & comic_info)
        # ComicInfo's LanguageISO has a country sibling; MetronInfo's only
        # country is a price attribute.
        assert "country" in comic_info
        assert "country" not in metron
        # reading_direction rides ComicInfo's Manga, not a canonical key of
        # its own.
        assert "reading_direction" in comic_info


class TagWriteDateTestCase(TestCase):
    """Composite tag-editor keys write through to the archive."""

    @override
    def setUp(self) -> None:
        cache.clear()
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.cbz_path = _TMP_DIR / "example.cbz"  # pyright: ignore[reportUninitializedInstanceVariable]
        shutil.copy(_EXAMPLE_CBZ, self.cbz_path)
        self.comic = _make_comic(self.cbz_path)  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _write(self, *, formats: tuple[str, ...] = ("COMIC_INFO",), **kwargs) -> None:
        task = BulkTagWriteTask(
            comic_pks=frozenset({self.comic.pk}),
            mode="update",
            formats=formats,
            **kwargs,
        )
        _make_writer().write_tags(task)

    def _write_metron(self, patch: dict) -> dict:
        """
        Write a MetronInfo patch to an archive that starts out untagged.

        The shared example fixture can't serve these: comicbox 4.8.5 raises
        sorting an existing localized name that carries no text, which every
        MetronInfo write to those fixtures trips over (a comicbox bug
        unrelated to the fields under test).
        """
        self.comic.path = str(_untagged_cbz(_TMP_DIR / "untagged.cbz"))
        self.comic.save()
        self._write(patch=patch, formats=("METRON_INFO",))
        return _read_sub_md(Path(self.comic.path))

    def test_write_date_parts(self) -> None:
        """A full trio lands in the archive."""
        self._write(patch={"date": dict(_DATE)})

        date = _read_sub_md(self.cbz_path).get("date", {})
        for part, value in _DATE.items():
            assert date.get(part) == value

    def test_partial_date_replaces_the_whole_date(self) -> None:
        """
        Update mode replaces a top-level key wholesale.

        The editor relies on this: it drops a cleared part from the
        replacement rather than sending a dotted delete key.
        """
        self._write(patch={"date": dict(_DATE)})
        self._write(patch={"date": {"year": _LATER_YEAR}})

        date = _read_sub_md(self.cbz_path).get("date", {})
        assert date.get("year") == _LATER_YEAR
        assert "month" not in date
        assert "day" not in date

    def test_delete_date_key_clears_the_date(self) -> None:
        self._write(patch={"date": dict(_DATE)})
        self._write(delete_keys=("date",))

        assert "date" not in _read_sub_md(self.cbz_path)

    def test_write_alternative_issue(self) -> None:
        """The alternative issue writes as its own nested issue object."""
        sub_md = self._write_metron({"issue": {"number": _ISSUE_NUMBER}})
        assert str(sub_md.get("issue", {}).get("number")) == _ISSUE_NUMBER

        # A second write patching only the alternate: replacing that key must
        # leave the issue proper — a separate top-level key — standing.
        self._write(
            patch={"alternative_issue": dict(_ALTERNATIVE_ISSUE)},
            formats=("METRON_INFO",),
        )

        sub_md = _read_sub_md(Path(self.comic.path))
        alternative = sub_md.get("alternative_issue", {})
        assert str(alternative.get("number")) == str(_ALTERNATIVE_ISSUE["number"])
        assert alternative.get("suffix") == _ALTERNATIVE_ISSUE["suffix"]
        assert str(sub_md.get("issue", {}).get("number")) == _ISSUE_NUMBER

    def test_write_collection_title(self) -> None:
        sub_md = self._write_metron({"collection_title": _COLLECTION_TITLE})

        assert sub_md.get("collection_title") == _COLLECTION_TITLE
