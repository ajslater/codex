"""
Per-collection-row aggregates must be exact under join fan-out.

Every number here is read off the wire: ``childCount`` / ``finished`` /
``progress`` from a browse, and ``pageCount`` / ``page`` from ``/metadata``,
which ships the raw sums. The fixtures deliberately create each fan-out
source the collection join can produce:

* a second user's bookmark on every comic, so the bare ``comic__bookmark``
  LEFT JOIN doubles every comic row on every request;
* two characters on one comic and one on the rest, so an ``characters``
  filter fans a *single* comic out (non-uniform, so the inflation does not
  cancel between the progress numerator and denominator);
* a comic in two ``StoryArcNumber`` rows of one arc;
* two publishers sharing a ``sort_name``, which the browse GROUP BY merges
  into one multi-id card.
"""

import json
import shutil
from typing import Final, override

import pytest
from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models import (
    Bookmark,
    Character,
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    StoryArc,
    Volume,
)
from codex.models.named import StoryArcNumber
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

TMP_DIR = tmp_dir("codex.tests.collection_row_aggregates")
_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_PAGES: Final = 24
_N: Final = 12
_TOTAL_PAGES: Final = _PAGES * _N
# ``progress`` is page * 100 / (page_count - 1), clamped to 100.
_SHOW_ALL: Final = {
    "publishers": True,
    "imprints": True,
    "series": True,
    "volumes": True,
}


def _v4(response):
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def _progress(page: int, page_count: int) -> float:
    return round(min(page * 100.0 / max(page_count - 1, 1), 100.0), 2)


class CollectionRowAggregateTestCase(TestCase):
    """The four collection-row aggregates under every fan-out source."""

    library: Library  # pyright: ignore[reportUninitializedInstanceVariable]
    root_folder: Folder  # pyright: ignore[reportUninitializedInstanceVariable]
    sub_folder: Folder  # pyright: ignore[reportUninitializedInstanceVariable]
    publisher: Publisher  # pyright: ignore[reportUninitializedInstanceVariable]
    imprint: Imprint  # pyright: ignore[reportUninitializedInstanceVariable]
    series: Series  # pyright: ignore[reportUninitializedInstanceVariable]
    volume: Volume  # pyright: ignore[reportUninitializedInstanceVariable]
    arc: StoryArc  # pyright: ignore[reportUninitializedInstanceVariable]
    char_a: Character  # pyright: ignore[reportUninitializedInstanceVariable]
    char_b: Character  # pyright: ignore[reportUninitializedInstanceVariable]
    comics: list[Comic]  # pyright: ignore[reportUninitializedInstanceVariable]
    me: User  # pyright: ignore[reportUninitializedInstanceVariable]
    other: User  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        """12 x 24-page issues in a series, a nested folder and an arc."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        sub = TMP_DIR / "sub"
        sub.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))
        self.root_folder = Folder.objects.create(
            library=self.library, path=str(TMP_DIR), name=TMP_DIR.name
        )
        self.sub_folder = Folder.objects.create(
            library=self.library,
            path=str(sub),
            name="sub",
            parent_folder=self.root_folder,
        )
        publisher = Publisher.objects.create(name="Pub")
        self.publisher = publisher
        self.imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        self.series = Series.objects.create(
            name="Ser", imprint=self.imprint, publisher=publisher
        )
        self.volume = Volume.objects.create(
            name=2024,
            series=self.series,
            imprint=self.imprint,
            publisher=publisher,
        )
        self.arc = StoryArc.objects.create(name="Arc")
        self.char_a = Character.objects.create(name="CharA")
        self.char_b = Character.objects.create(name="CharB")

        self.comics = []
        for n in range(1, _N + 1):
            path = sub / f"c{n:02}.cbz"
            path.touch()
            comic = Comic.objects.create(
                library=self.library,
                path=path,
                issue_number=n,
                name=f"C{n}",
                page_count=_PAGES,
                size=42,
                publisher=publisher,
                imprint=self.imprint,
                series=self.series,
                volume=self.volume,
                parent_folder=self.sub_folder,
            )
            comic.folders.set([self.root_folder, self.sub_folder])
            san = StoryArcNumber.objects.create(story_arc=self.arc, number=n)
            comic.story_arc_numbers.set([san])
            # Non-uniform m2m: only the first comic carries both characters.
            comic.characters.set(
                [self.char_a, self.char_b] if n == 1 else [self.char_a]
            )
            self.comics.append(comic)

        self.me = User.objects.create_user(username="me", password=_PW, is_staff=True)
        self.other = User.objects.create_user(username="other", password=_PW)
        for comic in self.comics:
            Bookmark.objects.create(user=self.other, comic=comic, page=5)
        self.client = Client()
        self.client.force_login(self.me)

    @override
    def tearDown(self) -> None:
        """Drop the fixture tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _finish(self, count: int, *, page: int | None = None) -> None:
        """Mark the first ``count`` comics finished for me."""
        Bookmark.objects.filter(user=self.me).delete()
        for comic in self.comics[:count]:
            Bookmark.objects.create(
                user=self.me,
                comic=comic,
                page=_PAGES - 1 if page is None else page,
                finished=True,
            )

    def _get(self, url: str, filters: dict | None = None):
        # ``filters`` and ``view_mode`` ride on every request: browse params
        # persist to saved settings, so an omitted one inherits the previous
        # request's value.
        params = {
            "filters": json.dumps(filters or {}),
            "search": "",
            "show": json.dumps(_SHOW_ALL),
            "view_mode": "cover",
        }
        response = self.client.get(url, params)
        if response.status_code in (302, 303):
            response = self.client.get(response.headers["Location"], params)
        assert response.status_code == _OK, (url, response.content)
        return _v4(response)

    def _row(self, collection: str, pks: str, filters: dict | None = None):
        rows = self._get(f"/api/v4/browse/{collection}/{pks}", filters)["collections"]
        assert len(rows) == 1, [r.get("name") for r in rows]
        return rows[0]

    def _assert_row(
        self, collection, pks, *, children, page, finished, filters=None
    ) -> None:
        """Assert a browse row and its /metadata twin agree and are exact."""
        row = self._row(collection, pks, filters)
        where = f"{collection}/{pks} filters={filters}"
        assert row["childCount"] == children, (where, "childCount", row["childCount"])
        assert row["finished"] == finished, (where, "finished", row["finished"])
        expected_progress = _progress(page, children * _PAGES)
        assert float(row["progress"]) == expected_progress, (
            where,
            "progress",
            row["progress"],
            expected_progress,
        )
        # /metadata ships the raw sums for the same node.
        ids = ",".join(str(pk) for pk in row["ids"])
        md = self._get(f"/api/v4/browse/{collection}/{ids}/metadata", filters)
        assert md["childCount"] == children, (where, "md childCount", md["childCount"])
        assert md["pageCount"] == children * _PAGES, (
            where,
            "md pageCount",
            md["pageCount"],
        )
        assert md["page"] == page, (where, "md page", md["page"])

    # ------------------------------------------------------------------
    # 12 x 24-page issues, 0 / 1 / 6 / 12 finished, per collection type
    # ------------------------------------------------------------------

    def _cases(self):
        """(label, collection, pks) for a series, a nested folder and an arc."""
        return (
            ("series", "imprints", str(self.imprint.pk)),
            ("volume", "series", str(self.series.pk)),
            ("folder", "folders", str(self.root_folder.pk)),
            ("arc", "arcs", "0"),
        )

    def test_unfiltered_counts(self) -> None:
        """Σ page_count and Σ page are exact with no user filter."""
        for n_finished, finished in ((0, False), (1, None), (6, None), (12, True)):
            self._finish(n_finished)
            for _label, collection, pks in self._cases():
                self._assert_row(
                    collection,
                    pks,
                    children=_N,
                    page=n_finished * _PAGES,
                    finished=finished,
                )

    def test_m2m_filter_counts(self) -> None:
        """A non-uniform m2m filter must not inflate the sums."""
        filters = {"characters": [self.char_a.pk, self.char_b.pk]}
        for n_finished, finished in ((0, False), (1, None), (6, None), (12, True)):
            self._finish(n_finished)
            for _label, collection, pks in self._cases():
                self._assert_row(
                    collection,
                    pks,
                    children=_N,
                    page=n_finished * _PAGES,
                    finished=finished,
                    filters=filters,
                )

    def test_finished_child_credits_full_page_count(self) -> None:
        """A finished child whose bookmark page is 3 of 24 still counts 24."""
        self._finish(1, page=3)
        for _label, collection, pks in self._cases():
            self._assert_row(collection, pks, children=_N, page=_PAGES, finished=None)

    def test_progress_is_proportional(self) -> None:
        """Progress must track the read fraction, not saturate at 100."""
        seen = []
        for n_finished in (0, 1, 6, 12):
            self._finish(n_finished)
            row = self._row("imprints", str(self.imprint.pk))
            seen.append(float(row["progress"]))
        assert seen == [
            0.0,
            _progress(_PAGES, _TOTAL_PAGES),
            _progress(6 * _PAGES, _TOTAL_PAGES),
            100.0,
        ], seen

    def test_duplicate_arc_row_can_report_finished(self) -> None:
        """
        A fully-read arc with a duplicated arc row must report read.

        ``StoryArc`` reaches Comic through ``StoryArcNumber``, and
        ``unique_together = ("story_arc", "number")`` lets one comic sit in
        two numbers of the same arc, which repeats its joined row. The
        counts are COUNT DISTINCT so they survive it; the two Σ aggregates
        cannot, and are asserted as the known gap below.
        """
        self._finish(_N)
        san_dup = StoryArcNumber.objects.create(story_arc=self.arc, number=99)
        self.comics[0].story_arc_numbers.add(san_dup)
        row = self._row("arcs", "0")
        assert row["childCount"] == _N, row["childCount"]
        assert row["finished"] is True, row["finished"]

    @pytest.mark.xfail(
        reason=(
            "Known gap: a Σ cannot survive a repeated joined row. StoryArc "
            "reaches Comic through StoryArcNumber, so a comic in two numbers "
            "of one arc counts its pages twice (browse: 312 not 288), and "
            "/metadata compounds it with its own arc-m2m display join (360). "
            "Only a pre-deduplicated comic set fixes it; the importer deletes "
            "stale arc links and the dev corpus has 0 of 171 such links. The "
            "counts are COUNT DISTINCT and are already exact."
        ),
        strict=True,
    )
    def test_duplicate_arc_row_sums(self) -> None:
        """A duplicated arc row must not inflate Σ page_count / Σ page."""
        self._finish(1)
        san_dup = StoryArcNumber.objects.create(story_arc=self.arc, number=99)
        self.comics[0].story_arc_numbers.add(san_dup)
        md = self._get("/api/v4/browse/arcs/1/metadata")
        assert md["childCount"] == _N, md["childCount"]
        assert md["pageCount"] == _TOTAL_PAGES, md["pageCount"]
        assert md["page"] == _PAGES, md["page"]


class MergedCardAggregateTestCase(TestCase):
    """Two publishers sharing a sort_name merge into one multi-id card."""

    library: Library  # pyright: ignore[reportUninitializedInstanceVariable]
    comics: dict[str, list[Comic]]  # pyright: ignore[reportUninitializedInstanceVariable]
    me: User  # pyright: ignore[reportUninitializedInstanceVariable]
    other: User  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        """Build "Pub" (12 x 24) and "PUB" (3 x 10), which merge into one card."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))
        self.comics = {}
        for tag, name, count, pages, start in (
            ("a", "Pub", 12, 24, 1),
            ("b", "PUB", 3, 10, 101),
        ):
            pub = Publisher.objects.create(name=name)
            imp = Imprint.objects.create(name=f"Imp{tag}", publisher=pub)
            ser = Series.objects.create(name=f"Ser{tag}", imprint=imp, publisher=pub)
            vol = Volume.objects.create(
                name=2000 + start, series=ser, imprint=imp, publisher=pub
            )
            comics = []
            for i in range(count):
                path = TMP_DIR / f"{tag}{i:03}.cbz"
                path.touch()
                comics.append(
                    Comic.objects.create(
                        library=self.library,
                        path=path,
                        issue_number=start + i,
                        name=f"C{start + i}",
                        page_count=pages,
                        size=42,
                        publisher=pub,
                        imprint=imp,
                        series=ser,
                        volume=vol,
                    )
                )
            self.comics[tag] = comics
        self.me = User.objects.create_user(username="me", password=_PW, is_staff=True)
        self.other = User.objects.create_user(username="other", password=_PW)
        for comics in self.comics.values():
            for comic in comics:
                Bookmark.objects.create(user=self.other, comic=comic, page=5)
        self.client = Client()
        self.client.force_login(self.me)

    @override
    def tearDown(self) -> None:
        """Drop the fixture tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def test_merged_card_aggregates_both_publishers(self) -> None:
        """The merged card's numbers must cover every merged pk."""
        for comic in self.comics["a"]:
            Bookmark.objects.create(user=self.me, comic=comic, page=3, finished=True)
        params = {
            "filters": "{}",
            "search": "",
            "show": json.dumps(_SHOW_ALL),
            "view_mode": "cover",
        }
        response = self.client.get("/api/v4/browse/publishers", params)
        assert response.status_code == _OK, response.content
        rows = _v4(response)["collections"]
        assert len(rows) == 1, [r.get("name") for r in rows]
        row = rows[0]
        assert len(row["ids"]) == 2, row["ids"]  # noqa: PLR2004
        # 12 x 24 + 3 x 10 = 318 pages over 15 comics; 12 read = 288 pages.
        assert row["childCount"] == 15, row["childCount"]  # noqa: PLR2004
        assert row["finished"] is None, row["finished"]
        assert float(row["progress"]) == _progress(288, 318), row["progress"]
