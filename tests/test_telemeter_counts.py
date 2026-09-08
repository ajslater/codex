"""
The comicbox 5 stats, counted against a real import.

Every count added for codex 2.3.0 reads zero on a library that has not been
read under comicbox 5, which makes zero the uninformative answer: a collector
that counts the wrong thing looks exactly like a library nobody re-read. So
these run the fixture through the importer and check the counts against tags
that are actually in the archive.
"""

from pathlib import Path
from typing import override

from codex.librarian.telemeter.count_stats import (
    get_comic_nonempty_stats,
    get_manga_stats,
    get_metadata_flag_stats,
)
from codex.models import Comic
from tests.importer.test_basic import PATH, BaseTestImporter, run_full_import


class TelemeterCountsTestCase(BaseTestImporter):
    """A full import of the fixture, then read the counts back."""

    @override
    def setUp(self) -> None:
        super().setUp()
        run_full_import(self.importer)

    def test_manga_counts_read_the_tag(self) -> None:
        """The fixture says ``manga: No``, and nothing else is in the library."""
        assert get_manga_stats() == {
            "comic_manga_yes_count": 0,
            "comic_manga_no_count": 1,
            "comic_manga_unknown_count": 0,
        }

    def test_flag_counts_read_the_rows(self) -> None:
        """
        Two primary credits and one alternative-name reprint.

        The fixture credits Joe Orlando as primary Writer and Wally Wood as
        primary Penciller, and carries one series alternative name beside its
        reprints.
        """
        assert get_metadata_flag_stats() == {
            "credit_primary_count": 2,
            "reprint_alternative_name_count": 1,
        }

    def test_nonempty_counts_read_the_columns(self) -> None:
        """The fixture carries a manga volume and web links."""
        assert get_comic_nonempty_stats() == {
            "comic_manga_volume_count": 1,
            "comic_urls_count": 1,
        }

    def test_an_empty_column_is_not_counted(self) -> None:
        """
        The regression test for the isnull trap.

        ``manga_volume`` and ``urls`` are NOT NULL with empty defaults, so the
        isnull idiom the older comic counts use would report the whole library
        for both. A second comic carrying neither must not move the count.
        """
        copy_path = Path(f"{PATH}.copy.cbz")
        copy_path.touch()  # presave stats the file
        comic = Comic.objects.get(path=PATH)
        comic.pk = None
        comic.path = str(copy_path)
        comic.manga_volume = ""
        comic.urls = []
        comic.save()

        assert Comic.objects.count() == 2  # noqa: PLR2004
        assert get_comic_nonempty_stats() == {
            "comic_manga_volume_count": 1,
            "comic_urls_count": 1,
        }
