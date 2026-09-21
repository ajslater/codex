"""
One unreadable comic must not empty an OPDS v1 feed.

``lazy_metadata`` opens the comic archive to backfill ``page_count`` /
``file_type`` for OPDS-PSE readers. It used to propagate whatever the
archive layer raised straight through the ``entries`` accessor, whose
``default_factory=list`` then returned a *fresh* empty list — discarding
every entry already built. Three comics, one of them 16 bytes of junk on
disk, rendered a ``200`` with zero entries.
"""

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Final
from xml.etree import ElementTree as ET

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import (
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.startup import init_admin_flags
from codex.views.opds.v1.const import OPDS1EntryData
from codex.views.opds.v1.entry.entry import OPDS1Entry

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_TMP_DIR: Final = Path("/tmp/codex.tests.opds.degrade")  # noqa: S108
_V1_ROOT: Final = "/opds/v1.2/"
_COMIC_COUNT: Final = 3
_GARBAGE: Final = b"not a comic!!!!!"  # the measured repro: a few bytes of junk


def _entry_titles(content: bytes) -> list[str]:
    """Every ``<atom:entry>``'s title text, namespace-blind."""
    root = ET.fromstring(content)  # noqa: S314 - server-rendered, trusted
    titles = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "entry":
            continue
        for child in element:
            if child.tag.rsplit("}", 1)[-1] == "title":
                titles.append((child.text or "").strip())
                break
    return titles


class _DegradeFixtureMixin:
    """A folder of three comics behind an authed client."""

    def setUp(self) -> None:
        """Build the library, the folder and three readable comics."""
        cache.clear()
        init_admin_flags()
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
        _TMP_DIR.mkdir(parents=True, exist_ok=True)

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="opds-degrade", password=_TEST_PASSWORD
        )
        self.client = Client()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client.force_login(self.user)

        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="PubDegrade")
        imprint = Imprint.objects.create(name="ImpDegrade", publisher=publisher)
        series = Series.objects.create(
            name="SeriesDegrade", publisher=publisher, imprint=imprint
        )
        volume = Volume.objects.create(
            name="1", publisher=publisher, imprint=imprint, series=series
        )
        folder_dir = _TMP_DIR / "folder1"
        folder_dir.mkdir(exist_ok=True)
        folder = Folder.objects.create(library=library, path=str(folder_dir))

        self.comic_pks: list[int] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for idx in range(1, _COMIC_COUNT + 1):
            path = folder_dir / f"c{idx}.cbz"
            path.write_bytes(_GARBAGE)
            comic = Comic.objects.create(
                library=library,
                path=path,
                issue_number=idx,
                name=f"ComicDegrade{idx}",
                publisher=publisher,
                imprint=imprint,
                series=series,
                volume=volume,
                parent_folder=folder,
                # Both set, so lazy_metadata short-circuits and never
                # opens the (junk) archive. The bad comic below clears
                # them to force the open.
                file_type="CBZ",
                page_count=1,
                size=len(_GARBAGE),
            )
            comic.folders.set([folder])
            self.comic_pks.append(comic.pk)
        self.folder_pk = folder.pk  # pyright: ignore[reportUninitializedInstanceVariable]

    def tearDown(self) -> None:
        """Remove the fixture tree."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _feed(self) -> bytes:
        """GET the folder's acquisition feed, asserting it is a 200."""
        cache.clear()
        # The feed normalizes its own query params with a 302 first.
        response = self.client.get(f"{_V1_ROOT}folders/{self.folder_pk}", follow=True)
        assert response.status_code == _HTTP_OK, response.content
        return response.content

    def _break_one_comic(self) -> str:
        """Clear the first comic's archive-derived fields; return its name."""
        comic = Comic.objects.get(pk=self.comic_pks[0])
        Comic.objects.filter(pk=comic.pk).update(page_count=0, file_type="")
        return comic.name


class OPDSDegradeFeedTestCase(_DegradeFixtureMixin, TestCase):
    """An unreadable archive degrades one entry, not the feed."""

    def test_healthy_feed_lists_every_comic(self) -> None:
        """Control: all three comics render while nothing opens an archive."""
        titles = _entry_titles(self._feed())
        for pk in self.comic_pks:
            name = Comic.objects.get(pk=pk).name
            assert any(name in title for title in titles), (
                f"{name} missing from {titles}"
            )

    def test_unreadable_comic_keeps_the_other_entries(self) -> None:
        """The feed keeps every entry it had built before the bad row."""
        before = _entry_titles(self._feed())
        self._break_one_comic()
        after = _entry_titles(self._feed())
        assert after, "one unreadable comic emptied the feed"
        assert len(after) == len(before), f"entries lost: {before} -> {after}"

    def test_unreadable_comic_degrades_to_a_db_only_entry(self) -> None:
        """The bad comic still gets an entry, minus the archive extras."""
        bad_name = self._break_one_comic()
        titles = _entry_titles(self._feed())
        assert any(bad_name in title for title in titles), (
            f"{bad_name} dropped instead of degraded: {titles}"
        )


class OPDSLazyMetadataTestCase(_DegradeFixtureMixin, TestCase):
    """``lazy_metadata`` swallows an unreadable archive."""

    @staticmethod
    def _entry(path: Path) -> OPDS1Entry:
        """Build an entry over a stand-in row with no archive metadata."""
        obj = SimpleNamespace(
            pk=1, path=str(path), page_count=0, file_type="", nav_collection="comics"
        )
        data = OPDS1EntryData(
            acquisition_collections=frozenset(),
            zero_pad=3,
            metadata=False,
            mime_type_map={},
        )
        return OPDS1Entry(obj, {}, data, title_filename_fallback=False)

    def test_corrupt_archive_returns_false(self) -> None:
        """A junk archive reports "nothing read" instead of raising."""
        entry = self._entry(_TMP_DIR / "folder1" / "c1.cbz")
        assert entry.lazy_metadata() is False

    def test_missing_file_returns_false(self) -> None:
        """A path that is not there reports "nothing read" instead of raising."""
        entry = self._entry(_TMP_DIR / "folder1" / "gone.cbz")
        assert entry.lazy_metadata() is False

    def test_failure_is_not_retried(self) -> None:
        """The second call short-circuits on the remembered failure."""
        entry = self._entry(_TMP_DIR / "folder1" / "c1.cbz")
        assert entry.lazy_metadata() is False
        assert entry.lazy_metadata() is False
