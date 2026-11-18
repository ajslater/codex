"""
The shelves filter must not multiply bookmark and page-count sums.

A shelved folder or story arc put ``folders`` / ``story_arc_numbers`` into
the filter as LEFT JOINs under the OR of the shelf's clauses. A comic that
matched another clause (here its series) then kept one joined row per
ancestor folder, so every ``Sum`` over the comic was multiplied by its
folder depth while the filter was on: "continue reading" opened at the
wrong page and card progress skewed.
"""

from typing import override

from codex.models import Bookmark, Comic, Folder, Shelf
from tests.shelf_fixtures import (
    HTTP_OK,
    SETTINGS_URL,
    TMP_DIR,
    ShelfTestCase,
    post_json,
    v4,
)

_PAGE_COUNT = 20
_DEEP_PAGE = 5
_SHALLOW_PAGE = 10


class ShelfFilterSumsTestCase(ShelfTestCase):
    """A shelf holding a folder and a series leaves the sums alone."""

    @override
    def setUp(self) -> None:
        super().setUp()
        top_dir = TMP_DIR / "top"
        mid_dir = top_dir / "mid"
        leaf_dir = mid_dir / "leaf"
        leaf_dir.mkdir(parents=True, exist_ok=True)
        top = Folder.objects.create(library=self.library, path=str(top_dir))
        mid = Folder.objects.create(
            library=self.library, parent_folder=top, path=str(mid_dir)
        )
        leaf = Folder.objects.create(
            library=self.library, parent_folder=mid, path=str(leaf_dir)
        )
        # c1 sits three folders deep; a second comic in the same volume one.
        self.c1.folders.set([top, mid, leaf])
        shallow_path = top_dir / "shallow.cbz"
        shallow_path.touch()
        self.shallow = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=self.library,
            path=shallow_path,
            issue_number=2,
            name="shallow",
            publisher=self.p1,
            imprint=self.i1,
            series=self.s1,
            volume=self.v1,
            parent_folder=top,
            size=1,
        )
        self.shallow.folders.set([top])
        Comic.objects.filter(pk__in=(self.c1.pk, self.shallow.pk)).update(
            page_count=_PAGE_COUNT
        )
        Bookmark.objects.create(user=self.user, comic=self.c1, page=_DEEP_PAGE)
        Bookmark.objects.create(user=self.user, comic=self.shallow, page=_SHALLOW_PAGE)
        self.shelf: Shelf = self._shelf()  # pyright: ignore[reportUninitializedInstanceVariable]
        self._put(self.shelf, "folders", top.pk)
        self._put(self.shelf, "series", self.s1.pk)
        response = post_json(
            self.client,
            "patch",
            SETTINGS_URL,
            {
                "show": {
                    "publishers": True,
                    "imprints": True,
                    "series": True,
                    "volumes": True,
                }
            },
        )
        assert response.status_code == HTTP_OK, response.content

    def _filter(self, *, on: bool) -> None:
        shelves = [self.shelf.pk] if on else []
        response = post_json(
            self.client, "patch", SETTINGS_URL, {"filters": {"shelves": shelves}}
        )
        assert response.status_code == HTTP_OK, response.content

    def _get(self, url: str) -> dict:
        response = self.client.get(url)
        assert response.status_code == HTTP_OK, response.content
        return v4(response)

    def _book_pages(self) -> dict[int, int]:
        data = self._get(f"/api/v4/browse/volumes/{self.v1.pk}?page=1")
        return {book["pk"]: book["page"] for book in data["books"]}

    def _volume_progress(self) -> dict[int, float]:
        data = self._get(f"/api/v4/browse/series/{self.s1.pk}?page=1")
        return {row["ids"][0]: row["progress"] for row in data["collections"]}

    def test_book_pages_are_not_multiplied(self) -> None:
        """Each book's bookmark page is its own, not page x folder depth."""
        expected = {self.c1.pk: _DEEP_PAGE, self.shallow.pk: _SHALLOW_PAGE}
        self._filter(on=False)
        assert self._book_pages() == expected
        self._filter(on=True)
        assert self._book_pages() == expected

    def test_collection_progress_is_not_skewed(self) -> None:
        """A volume's progress sums each comic once."""
        self._filter(on=False)
        unfiltered = self._volume_progress()
        # page / (page_count - 1): 15 / 39.
        assert unfiltered == {self.v1.pk: 38.46}
        self._filter(on=True)
        assert self._volume_progress() == unfiltered
