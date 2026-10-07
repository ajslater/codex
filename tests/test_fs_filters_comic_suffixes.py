"""
The scanner's comic suffixes come from comicbox, not from this host's tools.

Leaving a suffix out of the scan because its tool is missing made every
existing row of that type look deleted to the poller. comicbox 5.3.0's
RAR probe test-extracts a member, so it fails on more hosts than the path
check it replaced, and this is where that must not cost anyone a library.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from comicbox.box import Comicbox
from comicbox.enums.comicbox import FileTypeEnum

from codex.librarian.fs.filters import COMIC_SUFFIXES, match_comic


def test_suffixes_are_every_comicbox_file_type() -> None:
    """A format comicbox adds is scanned without anyone editing a list here."""
    assert {f".{ft.value.lower()}" for ft in FileTypeEnum} == COMIC_SUFFIXES
    assert {".cbz", ".cbr", ".cb7", ".cbt", ".pdf"} == COMIC_SUFFIXES


@pytest.mark.parametrize("name", ["a.cbz", "a.CBR", "a.cb7", "a.Cbt", "a.PDF"])
def test_every_file_type_matches_in_any_case(name: str) -> None:
    """The importer stores whatever case the filesystem had."""
    assert match_comic(Path(name))


@pytest.mark.parametrize("name", ["a.jpg", "a.zip", "a.cbz.part", "noext", ".cbz"])
def test_other_files_do_not_match(name: str) -> None:
    """Only a whole, known suffix is a comic."""
    assert not match_comic(Path(name))


def test_a_missing_tool_does_not_hide_its_comics() -> None:
    """Unreadable archives fail their import with the reason; they are still scanned."""
    with (
        patch.object(Comicbox, "is_unrar_supported", return_value=False),
        patch.object(Comicbox, "is_pdf_supported", return_value=False),
    ):
        assert match_comic(Path("/comics/a.cbr"))
        assert match_comic(Path("/comics/a.pdf"))
