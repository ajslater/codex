"""
The ``reprints`` browser table column and filter.

``Reprint`` is the only tag model without a ``name`` column — the label
composes from four — so both the table cell (Comic rows and collection-row
intersections) and the filter drawer need their own label paths. These
tests pin all of them to :meth:`Reprint.compose_name`'s output.
"""

import json
import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.choices.browser import DUMMY_NULL_NAME, VUETIFY_NULL_CODE
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.named import Reprint
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
TMP_DIR = Path("/tmp/codex.tests.browser_reprints_column")  # noqa: S108
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class _ReprintsFixtureTestCase(TestCase):
    """One publisher / imprint / series / volume and one comic to tag."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="Imp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = self._create_series("Ser")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic = self._create_comic("C1", 1)  # pyright: ignore[reportUninitializedInstanceVariable]
        user = User.objects.create_user(
            username="reprints_column_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _create_series(self, name: str) -> Series:
        return Series.objects.create(
            name=name, imprint=self.imprint, publisher=self.publisher
        )

    def _create_comic(
        self, name: str, issue_number: int, series: Series | None = None
    ) -> Comic:
        series = series or self.series
        volume, _ = Volume.objects.get_or_create(
            name=2024, series=series, imprint=self.imprint, publisher=self.publisher
        )
        path = TMP_DIR / f"{name.lower()}.cbz"
        path.touch()
        return Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=issue_number,
            name=name,
            publisher=self.publisher,
            imprint=self.imprint,
            series=series,
            volume=volume,
            size=42 + issue_number,
            year=2024,
            page_count=20,
        )

    def _set_view_mode_table(self) -> None:
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"viewMode": "table"}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _browse(self, url: str) -> dict:
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def _browse_comics(self, columns: str = "cover,name,reprints") -> dict:
        return self._browse(
            f"/api/v4/browse/series/{self.series.pk}?page=1&columns={columns}"
        )

    def _browse_series_rows(self, columns: str = "cover,name,reprints") -> dict:
        return self._browse(
            f"/api/v4/browse/publishers/{self.publisher.pk}?page=1&columns={columns}"
        )


class BrowserReprintsColumnTestCase(_ReprintsFixtureTestCase):
    """Table-cell display and sort for the composed alternate-series label."""

    def test_comic_row_composes_every_part(self) -> None:
        """The SQL expression renders the same label as ``Reprint.compose_name``."""
        reprints = (
            Reprint.objects.create(series_name="Kapitän Wissenschaft"),
            Reprint.objects.create(series_name="Capitan Sciencia", volume_number=1),
            Reprint.objects.create(series_name="Yearly", volume_number=1999),
            Reprint.objects.create(
                series_name="Full", volume_number=3, issue="2a", language="es"
            ),
        )
        self.comic.reprints.set(reprints)

        self._set_view_mode_table()
        row = self._browse_comics()["rows"][0]
        assert sorted(row["reprints"]) == sorted(
            reprint.name for reprint in reprints
        ), row
        # Spell the expectations out so a change to either the SQL or
        # the Python composer fails loudly instead of agreeing wrongly.
        # The aggregate sorts its own elements — identical reprint sets
        # must render identical JSON for the M2M sort to cluster them.
        assert row["reprints"] == [
            "Capitan Sciencia v1",
            "Full v3 #2a (es)",
            "Kapitän Wissenschaft",
            "Yearly (1999)",
        ]

    def test_collection_row_shows_only_shared_reprints(self) -> None:
        """A series row intersects its children's reprints."""
        shared = Reprint.objects.create(series_name="Shared", language="de")
        lonely = Reprint.objects.create(series_name="Lonely")
        self.comic.reprints.set((shared, lonely))
        sibling = self._create_comic("C2", 2)
        sibling.reprints.set((shared,))

        self._set_view_mode_table()
        row = self._browse_series_rows()["rows"][0]
        assert row["reprints"] == ["Shared (de)"], row

    def test_collection_row_without_reprints_is_empty(self) -> None:
        """Collections whose children carry no reprints render an empty cell."""
        self._set_view_mode_table()
        row = self._browse_series_rows()["rows"][0]
        assert row["reprints"] == [], row

    def test_collection_row_sort_by_reprints(self) -> None:
        """Sorting collection rows by the column uses its intersection SQL."""
        self.comic.reprints.add(
            Reprint.objects.create(series_name="Zulu", volume_number=2)
        )
        # "Zzz" has no reprints, so ascending by the column puts it
        # first — the opposite of the ``sort_name`` order the sort
        # falls back to when the intersection SQL isn't wired.
        self._create_comic("C2", 1, series=self._create_series("Zzz"))

        self._set_view_mode_table()
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"orderBy": "reprints", "orderReverse": False}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        rows = self._browse_series_rows()["rows"]
        assert [(row["name"], row["reprints"]) for row in rows] == [
            ("Zzz", []),
            ("Ser", ["Zulu v2"]),
        ], rows


class BrowserReprintsFilterTestCase(_ReprintsFixtureTestCase):
    """The filter drawer's choices and the resulting narrowing."""

    def test_choices_compose_labels(self) -> None:
        """The choices endpoint labels reprints like the metadata panel does."""
        reprint = Reprint.objects.create(
            series_name="Kapitän Wissenschaft", language="de"
        )
        self.comic.reprints.add(reprint)
        # A reprint-less sibling makes the view prepend the null
        # sentinel, which already carries a name of its own.
        self._create_comic("C2", 2)

        body = self._browse(f"/api/v4/browse/series/{self.series.pk}/choices/reprints")
        choices = {choice["pk"]: choice["name"] for choice in body["choices"]}
        assert choices[reprint.pk] == "Kapitän Wissenschaft (de)", choices
        assert choices[VUETIFY_NULL_CODE] == DUMMY_NULL_NAME, choices

    def test_choices_availability(self) -> None:
        """``reprints`` only offers a sub-menu once a value and a null exist."""
        body = self._browse(f"/api/v4/browse/series/{self.series.pk}/choices")
        assert body["reprints"] is False, body

        self.comic.reprints.add(Reprint.objects.create(series_name="Alt"))
        self._create_comic("C2", 2)
        cache.clear()
        body = self._browse(f"/api/v4/browse/series/{self.series.pk}/choices")
        assert body["reprints"] is True, body

    def test_filter_narrows_to_tagged_comics(self) -> None:
        """Selecting a reprint pk filters the browse to comics carrying it."""
        reprint = Reprint.objects.create(series_name="Alt", volume_number=1)
        self.comic.reprints.add(reprint)
        self._create_comic("C2", 2)

        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"filters": {"reprints": [reprint.pk]}}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        cache.clear()
        body = self._browse(f"/api/v4/browse/series/{self.series.pk}?page=1")
        names = [book["name"] for book in body["books"]]
        assert names == ["C1"], body


class BrowserAlternateNumberSortTestCase(_ReprintsFixtureTestCase):
    """Sorting by the alternate series' issue number (ComicInfo AlternateNumber)."""

    def _tag(self, comic: Comic, issue: str, series_name: str = "Crossover") -> Reprint:
        """Put ``comic`` in an alternate series at ``issue``."""
        reprint = Reprint.objects.create(series_name=series_name, issue=issue)
        comic.reprints.add(reprint)
        return reprint

    def _set_settings(self, **settings) -> None:
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(settings),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        cache.clear()

    def _book_names(self) -> list[str]:
        body = self._browse(f"/api/v4/browse/series/{self.series.pk}?page=1")
        return [book["name"] for book in body["books"]]

    def test_sorts_numerically_not_lexically(self) -> None:
        """#2 sorts before #10 — the whole point of the derived columns."""
        # ``self.comic`` is C1. Issue numbers are deliberately the
        # reverse of the alternate numbers so a fallback to the regular
        # issue sort can't accidentally produce the expected order.
        self._tag(self.comic, "2")
        reprints = [self._tag(self._create_comic("C2", 2), "10")]
        reprints.append(self._tag(self._create_comic("C3", 3), "3"))
        reprints.append(Reprint.objects.get(issue="2"))

        self._set_settings(
            orderBy="alternate_number",
            orderReverse=False,
            filters={"reprints": [reprint.pk for reprint in reprints]},
        )
        assert self._book_names() == ["C1", "C3", "C2"]

    def test_reverse_sort(self) -> None:
        """Reversing the alternate number sort reverses the books."""
        first = self._tag(self.comic, "2")
        second = self._tag(self._create_comic("C2", 2), "10")

        self._set_settings(
            orderBy="alternate_number",
            orderReverse=True,
            filters={"reprints": [first.pk, second.pk]},
        )
        assert self._book_names() == ["C2", "C1"]

    def test_suffix_breaks_ties(self) -> None:
        """Alternate numbers sharing a number order by their suffix."""
        plain = self._tag(self.comic, "2")
        suffixed = self._tag(self._create_comic("C2", 2), "2a")

        self._set_settings(
            orderBy="alternate_number",
            orderReverse=False,
            filters={"reprints": [plain.pk, suffixed.pk]},
        )
        assert self._book_names() == ["C1", "C2"]

    def test_untagged_comic_falls_back_to_its_issue_number(self) -> None:
        """A comic with no alternate number sorts by its own issue number."""
        # C1 carries alternate number 2; C2 has no alternate series and
        # issue #50. The fallback sorts C2 by 50, i.e. last. Without it
        # C2's key would be NULL, which SQLite sorts *first* ascending —
        # so the expected order only holds if the fallback is applied.
        tagged = self._tag(self.comic, "2")
        self._create_comic("C2", 50)

        self._set_settings(
            orderBy="alternate_number",
            orderReverse=False,
            filters={"reprints": [tagged.pk, VUETIFY_NULL_CODE]},
        )
        assert self._book_names() == ["C1", "C2"]

    def test_without_filter_degrades_to_issue_sort(self) -> None:
        """With no alternate series selected the sort is the plain issue sort."""
        self._tag(self.comic, "10")
        self._create_comic("C2", 2)
        self._create_comic("C3", 3)

        self._set_settings(orderBy="alternate_number", orderReverse=False)
        assert self._book_names() == ["C1", "C2", "C3"]

    def test_collection_rows_sort_by_child_alternate_number(self) -> None:
        """Series rows aggregate their children's alternate numbers."""
        self._tag(self.comic, "10")
        other_series = self._create_series("Aaa")
        early = self._tag(self._create_comic("C2", 2, series=other_series), "3")

        self._set_settings(
            orderBy="alternate_number",
            orderReverse=False,
            filters={"reprints": [early.pk, Reprint.objects.get(issue="10").pk]},
        )
        body = self._browse(f"/api/v4/browse/publishers/{self.publisher.pk}?page=1")
        names = [collection["name"] for collection in body["collections"]]
        assert names == ["Aaa", "Ser"], body


class BrowserReprintsCoverSortTestCase(_ReprintsFixtureTestCase):
    """The Alternate Series sort outside table view (cover cards, OPDS)."""

    def test_cover_view_sorts_comics_by_label(self) -> None:
        """Cover view can sort by the M2M label without a missing-alias error."""
        # The ORDER BY alias for an M2M primary sort used to be annotated
        # only in table view, so this request raised a FieldError.
        self.comic.reprints.add(Reprint.objects.create(series_name="Zulu"))
        sibling = self._create_comic("C2", 2)
        sibling.reprints.add(Reprint.objects.create(series_name="Alpha"))

        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(
                {"orderBy": "reprints", "orderReverse": False, "viewMode": "cover"}
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        cache.clear()
        body = self._browse(f"/api/v4/browse/series/{self.series.pk}?page=1")
        assert [book["name"] for book in body["books"]] == ["C2", "C1"], body

    def test_untagged_comic_falls_back_to_series_name(self) -> None:
        """A comic with no alternate series sorts by its real series name."""
        # All three live in series "Ser" (sort_name "ser"). C1 and C3
        # carry alternate series that bracket it alphabetically, so the
        # untagged C2 must land *between* them. Without the fallback its
        # key would be the empty aggregate and it would clump at one end.
        self.comic.reprints.add(Reprint.objects.create(series_name="zzz"))
        self._create_comic("C2", 2)
        self._create_comic("C3", 3).reprints.add(
            Reprint.objects.create(series_name="aaa")
        )

        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(
                {"orderBy": "reprints", "orderReverse": False, "viewMode": "cover"}
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        cache.clear()
        body = self._browse(f"/api/v4/browse/series/{self.series.pk}?page=1")
        assert [book["name"] for book in body["books"]] == ["C3", "C2", "C1"], body

    def test_alternate_series_works_as_a_multi_sort_extra(self) -> None:
        """A secondary sort on the column resolves its ORDER BY alias."""
        # ``reprints`` sorts through a fallback alias, which has to be
        # annotated for extras too, not just the primary key.
        self.comic.reprints.add(Reprint.objects.create(series_name="zzz"))
        self._create_comic("C2", 2)

        self._set_view_mode_table()
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps(
                {
                    "orderBy": "sort_name",
                    "orderExtraKeys": [{"key": "reprints", "reverse": False}],
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        cache.clear()
        rows = self._browse_comics()["rows"]
        assert {row["name"] for row in rows} == {"C1", "C2"}, rows
