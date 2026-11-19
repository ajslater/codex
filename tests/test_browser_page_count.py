"""
The browser's page count agrees with the pages the paginator serves.

The paginator lets the last page absorb up to five orphan rows (none for
folders and searches), but the page count was a plain ``ceil(count / page
size)``. A 15-row view with a page size of 6 showed three pages in the nav
bar while the paginator served two, and page 3 came back empty instead of
redirecting. Folder views put the subfolders first and fill the last folder
page with comics, so the same contract is walked there too.
"""

import shutil
from http import HTTPStatus
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.models import (
    AdminFlag,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
TMP_DIR: Final = tmp_dir("codex.tests.browser_page_count")
_PAGE_SIZE: Final = 6


def _v4(response) -> dict:
    """Unwrap the v4 ``{data, meta, errors}`` envelope."""
    return response.json()["data"]


class BrowserPageCountTestCase(TestCase):
    """Walk every page of a listing and compare it to the page count."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        AdminFlag.objects.filter(
            key=AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value
        ).update(value=str(_PAGE_SIZE))
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="Imp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = self._create_series("Ser")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.root_folder = Folder.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=self.library, path=str(TMP_DIR), name=TMP_DIR.name
        )
        self.issue_number = 0  # pyright: ignore[reportUninitializedInstanceVariable]
        user = User.objects.create_user(
            username="browser_page_count_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _create_series(self, name: str) -> Series:
        series = Series.objects.create(
            name=name, imprint=self.imprint, publisher=self.publisher
        )
        Volume.objects.create(
            name=2024, series=series, imprint=self.imprint, publisher=self.publisher
        )
        return series

    def _create_comic(
        self, parent_folder: Folder, series: Series | None = None
    ) -> Comic:
        series = series or self.series
        self.issue_number += 1
        path = Path(parent_folder.path) / f"c{self.issue_number}.cbz"
        path.touch()
        comic = Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=self.issue_number,
            name=f"C{self.issue_number}",
            publisher=self.publisher,
            imprint=self.imprint,
            series=series,
            volume=Volume.objects.get(series=series),
            parent_folder=parent_folder,
            size=1,
        )
        folders = [parent_folder]
        if parent_folder != self.root_folder:
            folders.append(self.root_folder)
        comic.folders.add(*folders)
        return comic

    def _create_subfolder(self, index: int) -> Folder:
        path = TMP_DIR / f"sub{index:02}"
        path.mkdir(exist_ok=True)
        folder = Folder.objects.create(
            library=self.library,
            path=str(path),
            name=path.name,
            parent_folder=self.root_folder,
        )
        # A folder only lists when it holds a comic.
        self._create_comic(folder)
        return folder

    def _get(self, url: str, page: int):
        cache.clear()
        return self.client.get(f"{url}?page={page}")

    def _walk(self, url: str) -> tuple[int, list[list[tuple[str, int]]]]:
        """Return the page count and every page's rows, then check one past it."""
        body = _v4(self._get(url, 1))
        num_pages = body["numPages"]
        pages = []
        for page in range(1, num_pages + 1):
            response = self._get(url, page)
            assert response.status_code == HTTPStatus.OK, (page, response.content)
            body = _v4(response)
            assert body["numPages"] == num_pages, page
            rows = [("collection", card["pk"]) for card in body["collections"]]
            rows += [("book", card["pk"]) for card in body["books"]]
            pages.append(rows)
        past = self._get(url, num_pages + 1)
        assert past.status_code == HTTPStatus.SEE_OTHER, past.content
        assert _v4(past)["route"]["params"]["page"] == num_pages
        return num_pages, pages

    def _assert_pages(
        self, url: str, expected_rows: list[tuple[str, int]], page_sizes: list[int]
    ) -> None:
        num_pages, pages = self._walk(url)
        assert [len(rows) for rows in pages] == page_sizes
        assert num_pages == len(page_sizes)
        served = [row for rows in pages for row in rows]
        # Every row once, none twice.
        assert sorted(served) == sorted(expected_rows)

    def test_last_page_absorbs_orphans(self) -> None:
        """15 books at 6 a page are 2 pages: the last takes the 3 orphans."""
        comics = [self._create_comic(self.root_folder) for _ in range(15)]
        self._assert_pages(
            f"/api/v4/browse/series/{self.series.pk}",
            [("book", comic.pk) for comic in comics],
            [6, 9],
        )

    def test_orphan_limit_starts_a_new_page(self) -> None:
        """18 books leave 6 over the first two pages: past the orphan limit."""
        comics = [self._create_comic(self.root_folder) for _ in range(18)]
        self._assert_pages(
            f"/api/v4/browse/series/{self.series.pk}",
            [("book", comic.pk) for comic in comics],
            [6, 6, 6],
        )

    def test_collections_absorb_orphans(self) -> None:
        """Collection listings count pages the same way: 10 series are 1 page."""
        # The setUp series has no comics, so the listing leaves it out.
        series = [self._create_series(f"S{index:02}") for index in range(10)]
        for one_series in series:
            self._create_comic(self.root_folder, one_series)
        self._assert_pages(
            f"/api/v4/browse/publishers/{self.publisher.pk}",
            [("collection", one_series.pk) for one_series in series],
            [10],
        )

    def test_folder_books_follow_the_last_folder_page(self) -> None:
        """
        Folders come first; comics start on the last folder page.

        Folders take no orphans, so 8 subfolders and 5 comics at 6 a page are
        6 folders, then 2 folders and 4 comics, then the last comic.
        """
        subfolders = [self._create_subfolder(index) for index in range(8)]
        comics = [self._create_comic(self.root_folder) for _ in range(5)]
        self._assert_pages(
            f"/api/v4/browse/folders/{self.root_folder.pk}",
            [("collection", folder.pk) for folder in subfolders]
            + [("book", comic.pk) for comic in comics],
            [6, 6, 1],
        )

    def test_folder_books_after_a_full_folder_page(self) -> None:
        """When the folders fill their last page, comics start the next one."""
        subfolders = [self._create_subfolder(index) for index in range(6)]
        comics = [self._create_comic(self.root_folder) for _ in range(4)]
        self._assert_pages(
            f"/api/v4/browse/folders/{self.root_folder.pk}",
            [("collection", folder.pk) for folder in subfolders]
            + [("book", comic.pk) for comic in comics],
            [6, 4],
        )
