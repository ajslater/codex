"""
Mark Unread rewinds the bookmark page, keeps the row, and creates nothing.

"Mark Read" and "Mark Unread" from a browser card's menu and from the
select-many toolbar both PATCH ``{"finished": <bool>}`` and nothing else, so
before this the bookmark's ``page`` survived being marked unread: a comic read
to the end and then marked unread still reported ``progress`` near 100 and
rendered as nearly finished.

The rewind has to happen server-side. ``BookmarkView`` validates every
recursive (non-comic) target through ``BookmarkFinishedSerializer``, whose
``fields`` is ``("finished",)``, so a ``page`` sent by the client is dropped on
exactly the containers bulk mark-unread is used on.

The rewind is also why the reader can send ``{page, finished: False}`` as one
payload when it pages back through a finished comic: the rewind only fires for
a bare ``{"finished": False}``, so a combined write keeps its position and
clears the flag.

It must also not CREATE rows. ``Bookmark.page`` is nullable with no default and
``finished`` defaults to False, so a row holding ``page=0, finished=False`` is
indistinguishable from no row at all to every consumer -- writing one per
never-opened comic in the target is pure cost.
"""

import json
import shutil
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models import (
    Bookmark,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

TMP_DIR = tmp_dir("codex.tests.bookmark_mark_unread")
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_PAGE_COUNT: Final = 24
_COMIC_COUNT: Final = 4
# Arbitrary mid-book bookmark positions the rewind must not touch.
_PART_READ_PAGE: Final = 5
_EXPLICIT_PAGE: Final = 7
_TURNED_TO_PAGE: Final = 11


class MarkUnreadTestCase(TestCase):
    """One publisher of four comics, one of them read to the end."""

    @override
    def setUp(self) -> None:
        """Build the tree and log in."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )
        self.publisher = publisher  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comics: list[Comic] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for n in range(1, _COMIC_COUNT + 1):
            path = TMP_DIR / f"c{n}.cbz"
            path.touch()
            self.comics.append(
                Comic.objects.create(
                    library=library,
                    path=path,
                    issue_number=n,
                    name=f"C{n}",
                    publisher=publisher,
                    imprint=imprint,
                    series=series,
                    volume=volume,
                    page_count=_PAGE_COUNT,
                    size=42,
                )
            )
        self.me = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="me", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.me)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _patch_comic(self, comic, data: dict) -> None:
        self._patch(f"/api/v4/comics/{comic.pk}/bookmark", data)

    def _patch_collection(self, collection: str, pk: int, data: dict) -> None:
        self._patch(f"/api/v4/browse/{collection}/{pk}/bookmark", data)

    def _patch(self, url: str, data: dict) -> None:
        response = self.client.patch(url, data=data, content_type="application/json")
        assert response.status_code == _HTTP_OK, (url, response.status_code)

    def _my_bookmark(self, comic) -> Bookmark | None:
        return Bookmark.objects.filter(user=self.me, comic=comic).first()

    def test_mark_unread_rewinds_the_page(self) -> None:
        """The row survives with page 0 rather than keeping its position."""
        comic = self.comics[0]
        Bookmark.objects.create(
            user=self.me, comic=comic, page=_PAGE_COUNT - 1, finished=True
        )
        self._patch_comic(comic, {"finished": False})
        bookmark = self._my_bookmark(comic)
        assert bookmark is not None, "the row must not be deleted"
        assert bookmark.page == 0, bookmark.page
        assert bookmark.finished is False

    def test_mark_read_leaves_the_page_alone(self) -> None:
        """Only ``finished: False`` rewinds; marking read must not."""
        comic = self.comics[0]
        Bookmark.objects.create(
            user=self.me, comic=comic, page=_PART_READ_PAGE, finished=False
        )
        self._patch_comic(comic, {"finished": True})
        bookmark = self._my_bookmark(comic)
        assert bookmark is not None
        assert bookmark.page == _PART_READ_PAGE, bookmark.page
        assert bookmark.finished is True

    def test_explicit_page_wins(self) -> None:
        """A caller that sends its own page is not second-guessed."""
        comic = self.comics[0]
        Bookmark.objects.create(user=self.me, comic=comic, page=20, finished=True)
        self._patch_comic(comic, {"finished": False, "page": _EXPLICIT_PAGE})
        bookmark = self._my_bookmark(comic)
        assert bookmark is not None
        assert bookmark.page == _EXPLICIT_PAGE, bookmark.page

    def test_reader_page_turn_is_untouched(self) -> None:
        """A bare page write never trips the rewind."""
        comic = self.comics[0]
        self._patch_comic(comic, {"page": _TURNED_TO_PAGE})
        bookmark = self._my_bookmark(comic)
        assert bookmark is not None
        assert bookmark.page == _TURNED_TO_PAGE, bookmark.page

    def test_re_reading_a_finished_comic_puts_it_back_in_progress(self) -> None:
        """
        The reader's backward page turn, end to end.

        ``{page, finished: False}`` is what the reader store sends when it
        pages below the last page of a comic whose bookmark says finished.
        Both halves have to land -- the position kept, the flag cleared --
        or Keep Reading never shows a comic while it is being re-read.
        ``test_explicit_page_wins`` pins the page half; this pins the flag
        and what the filters make of it.
        """
        comic = self.comics[0]
        Bookmark.objects.create(
            user=self.me, comic=comic, page=_PAGE_COUNT - 1, finished=True
        )
        self._patch_comic(comic, {"page": _PART_READ_PAGE, "finished": False})
        bookmark = self._my_bookmark(comic)
        assert bookmark is not None
        assert bookmark.page == _PART_READ_PAGE, bookmark.page
        assert bookmark.finished is False
        assert self._filter_count("IN_PROGRESS") == 1
        assert self._filter_count("READ") == 0

    def test_mark_unread_creates_no_rows(self) -> None:
        """
        Marking a mostly-unopened collection unread writes nothing new.

        A missing row already reads as unread everywhere, so creating one per
        never-opened child is pure cost -- 497 rows for a 500-issue publisher
        with 3 read.
        """
        read = self.comics[0]
        Bookmark.objects.create(
            user=self.me, comic=read, page=_PAGE_COUNT - 1, finished=True
        )
        assert Bookmark.objects.count() == 1
        self._patch_collection("publishers", self.publisher.pk, {"finished": False})
        assert Bookmark.objects.count() == 1, list(
            Bookmark.objects.values_list("comic_id", "page", "finished")
        )
        bookmark = self._my_bookmark(read)
        assert bookmark is not None
        assert bookmark.page == 0, bookmark.page
        assert bookmark.finished is False

    def test_mark_read_still_creates_rows(self) -> None:
        """The create path is only skipped for mark-unread."""
        self._patch_collection("publishers", self.publisher.pk, {"finished": True})
        assert Bookmark.objects.count() == _COMIC_COUNT, Bookmark.objects.count()
        assert Bookmark.objects.filter(finished=True).count() == _COMIC_COUNT

    def test_marked_unread_comic_is_unread_and_not_in_progress(self) -> None:
        """The rewound row must not read as in-progress to the filters."""
        comic = self.comics[0]
        Bookmark.objects.create(
            user=self.me, comic=comic, page=_PAGE_COUNT - 1, finished=True
        )
        self._patch_comic(comic, {"finished": False})
        assert self._filter_count("UNREAD") == _COMIC_COUNT
        assert self._filter_count("IN_PROGRESS") == 0
        assert self._filter_count("READ") == 0

    def _filter_count(self, bookmark_filter: str) -> int:
        params = {"filters": json.dumps({"bookmark": bookmark_filter}), "search": ""}
        response = self.client.get("/api/v4/browse/comics", params)
        if response.status_code in (302, 303):
            response = self.client.get(response.headers["Location"])
        assert response.status_code == _HTTP_OK, response.content
        body = response.json()
        data = body.get("data", body)
        return data["count"]
