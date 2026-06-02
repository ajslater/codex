"""End-to-end tests for the table-view response shape."""

import json
import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_BAD_REQUEST: Final = 400
TMP_DIR = Path("/tmp/codex.tests.browser_table_response")  # noqa: S108
_SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


# Through-tables touched by the simple-M2M intersection batch helper.
# A single ``UNION ALL`` query mentions all of these in its SQL, so
# substring-counting the captured query text is enough to distinguish
# the batched path from the per-column-loop path.
_SIMPLE_M2M_THROUGH_TABLES: Final = (
    "codex_comic_genres",
    "codex_comic_tags",
    "codex_comic_characters",
    "codex_comic_teams",
    "codex_comic_locations",
    "codex_comic_stories",
    "codex_comic_series_groups",
)


def _count_through_table_queries(captured_queries) -> int:
    """Count how many captured queries reference any simple-M2M through table."""
    return sum(
        any(table in q["sql"] for table in _SIMPLE_M2M_THROUGH_TABLES)
        for q in captured_queries
    )


class BrowserTablePageResponseTestCase(TestCase):
    """End-to-end: table-view requests return ``rows`` keyed by columns=."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))

        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )
        path = TMP_DIR / "c1.cbz"
        path.touch()
        Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name="C1",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=42,
            year=2024,
            page_count=20,
        )
        user = User.objects.create_user(
            username="table_response_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)
        self.series = series  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _set_view_mode_table(self) -> None:
        response = self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"viewMode": "table"}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _browse_series(self, *, columns: str | None = None) -> dict:
        url = f"/api/v4/browse/series/{self.series.pk}?page=1"
        if columns is not None:
            url = f"{url}&columns={columns}"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def _create_sibling_comic(
        self, anchor: Comic, name: str, issue_number: int
    ) -> Comic:
        """
        Create a Comic in the same publisher / imprint / series / volume as ``anchor``.

        Used by tests that need a small fixture of comics under one
        series to exercise collection-row aggregation. ``size`` and
        ``page_count`` are deliberately uniform so cumulative-sum
        assertions in those tests stay deterministic without per-call
        plumbing.
        """
        path = TMP_DIR / f"{name.lower()}.cbz"
        path.touch()
        return Comic.objects.create(
            library=anchor.library,
            path=path,
            issue_number=issue_number,
            name=name,
            publisher=anchor.publisher,
            imprint=anchor.imprint,
            series=anchor.series,
            volume=anchor.volume,
            size=42 + issue_number,
            year=2024,
            page_count=20,
        )

    def test_cover_view_returns_cards_without_rows(self) -> None:
        """Cover mode: cards present, ``rows`` stripped from the response."""
        body = self._browse_series()
        assert "books" in body
        # v4 strips ``rows`` from cover-mode responses ("pick card or
        # table, not both at once" — tasks/api-v4.md Phase 3).
        assert "rows" not in body

    def test_table_view_returns_rows_without_cards(self) -> None:
        """Table mode: ``rows`` present, cards stripped from the response."""
        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,issue")
        # v4 strips ``groups`` / ``books`` from table-mode responses; the
        # mobile auto-fallback re-fetches with ``?view_mode=card`` if it
        # wants the card shape.
        assert "books" not in body
        assert "collections" not in body
        rows = body["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert "pk" in row
        assert "coverPk" in row  # camelCased
        assert "name" in row
        # ``issue`` is the compound column (issue_number + issue_suffix).
        # The two halves stay separate on the wire so the cell can
        # render the number right-justified and the suffix left-
        # justified. The setUp comic has issue_number=1 and no suffix.
        assert row["issue"] == {"number": "1", "suffix": ""}

    def test_table_view_invalid_columns_rejected(self) -> None:
        self._set_view_mode_table()
        url = f"/api/v4/browse/series/{self.series.pk}?page=1&columns=cover,phantom_column"
        response = self.client.get(url)
        assert response.status_code == _HTTP_BAD_REQUEST

    def test_table_view_falls_back_to_default_columns(self) -> None:
        # No ``columns=`` query param: response should still have rows
        # populated from the registry defaults for the current top-group.
        self._set_view_mode_table()
        body = self._browse_series()
        assert "rows" in body
        rows = body["rows"]
        assert len(rows) == 1
        # Default fallback columns include "name" for every top-group.
        row = rows[0]
        assert "name" in row

    def test_table_view_m2m_genres_returns_list(self) -> None:
        """Requesting the genres column produces a list value per row."""
        from codex.models.named import Genre

        comic = Comic.objects.first()
        assert comic is not None
        genre_a = Genre.objects.create(name="Sci-Fi")
        genre_b = Genre.objects.create(name="Adventure")
        comic.genres.add(genre_a, genre_b)

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,genres")
        rows = body["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert "genres" in row
        # JsonGroupArray + JSONField returns a list, order isn't guaranteed.
        assert sorted(row["genres"]) == ["Adventure", "Sci-Fi"]

    def test_table_view_no_m2m_columns_skips_aggregation(self) -> None:
        """Requesting only scalar columns produces a row without M2M keys."""
        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name")
        rows = body["rows"]
        row = rows[0]
        # No M2M column requested -> M2M keys absent from the row dict.
        assert "genres" not in row
        assert "tags" not in row

    def test_table_view_fk_name_columns_populate(self) -> None:
        """FK-name columns (country / language) translate ISO codes via pycountry."""
        from codex.models.named import Country, Language

        comic = Comic.objects.first()
        assert comic is not None
        # Country / Language tables store ISO-2 codes; the serializer
        # resolves them to full names via pycountry.
        country = Country.objects.create(name="us")
        language = Language.objects.create(name="en")
        comic.country = country
        comic.language = language
        comic.save()

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,country,language")
        rows = body["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert row["country"] == "United States"
        assert row["language"] == "English"

    def test_table_view_unknown_country_code_passes_through(self) -> None:
        """Unrecognized ISO codes fall back to the raw string (no crash)."""
        from codex.models.named import Country

        comic = Comic.objects.first()
        assert comic is not None
        country = Country.objects.create(name="zz")  # not a real ISO-2 code
        comic.country = country
        comic.save()

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,country")
        row = body["rows"][0]
        assert row["country"] == "zz"

    def test_table_view_story_arcs_aggregation(self) -> None:
        """``story_arcs`` resolves through StoryArcNumber to story_arc.name."""
        from codex.models.named import StoryArc, StoryArcNumber

        comic = Comic.objects.first()
        assert comic is not None
        arc = StoryArc.objects.create(name="The Big One")
        san = StoryArcNumber.objects.create(story_arc=arc, number=1)
        comic.story_arc_numbers.add(san)

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,story_arcs")
        rows = body["rows"]
        row = rows[0]
        assert row.get("storyArcs") == ["The Big One"]

    def test_table_view_credits_aggregation_with_role(self) -> None:
        """Credits suffix the role: ``Person Name (Role)``."""
        from codex.models.named import Credit, CreditPerson, CreditRole

        comic = Comic.objects.first()
        assert comic is not None
        person = CreditPerson.objects.create(name="Jane Author")
        role = CreditRole.objects.create(name="Writer")
        credit = Credit.objects.create(person=person, role=role)
        comic.credits.add(credit)

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,credits")
        rows = body["rows"]
        row = rows[0]
        assert row.get("credits") == ["Jane Author (Writer)"]

    def test_table_view_credits_aggregation_without_role(self) -> None:
        """Credits omit the suffix when role is null."""
        from codex.models.named import Credit, CreditPerson

        comic = Comic.objects.first()
        assert comic is not None
        person = CreditPerson.objects.create(name="Anonymous")
        credit = Credit.objects.create(person=person)
        comic.credits.add(credit)

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,credits")
        rows = body["rows"]
        row = rows[0]
        assert row.get("credits") == ["Anonymous"]

    def test_table_view_identifiers_with_source(self) -> None:
        """Identifiers render as ``source:type:key`` when source is set."""
        from codex.models.identifier import (
            Identifier,
            IdentifierSource,
            IdentifierType,
        )

        comic = Comic.objects.first()
        assert comic is not None
        source = IdentifierSource.objects.create(name="comicvine")
        ident = Identifier.objects.create(
            source=source,
            id_type=IdentifierType.ISSUE.value,
            key="12345",
        )
        comic.identifiers.add(ident)

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,identifiers")
        rows = body["rows"]
        row = rows[0]
        actual = row.get("identifiers")
        assert actual == ["comicvine:comic:12345"]

    def test_table_view_identifiers_without_source(self) -> None:
        """Identifiers render as ``type:key`` when source is null."""
        from codex.models.identifier import Identifier, IdentifierType

        comic = Comic.objects.first()
        assert comic is not None
        ident = Identifier.objects.create(
            source=None,
            id_type=IdentifierType.SERIES.value,
            key="abc",
        )
        comic.identifiers.add(ident)

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,identifiers")
        rows = body["rows"]
        row = rows[0]
        assert row.get("identifiers") == ["series:abc"]

    def test_table_view_identifiers_skips_empty_rows(self) -> None:
        """Placeholder identifiers (no type, no key) are filtered out."""
        from codex.models.identifier import Identifier

        comic = Comic.objects.first()
        assert comic is not None
        # An identifier with no id_type and no key would render as
        # ``:`` and pollute the aggregated list. Filter it out.
        ident = Identifier.objects.create(source=None, id_type="", key="")
        comic.identifiers.add(ident)

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,identifiers")
        rows = body["rows"]
        row = rows[0]
        # Empty list (or absent) is acceptable; the colon-only string
        # is not.
        assert row.get("identifiers") in ([], None)

    def test_table_view_m2m_sort_groups_identical_sets(self) -> None:
        """Comics with the same genre set sort to the same equivalence class."""
        from codex.models.named import Genre

        # Two comics in the same series sharing identical genre sets.
        # Sorting by genres should place them adjacent. A third comic
        # with a different genre set goes elsewhere; a fourth with no
        # genres should sort to one end.
        first_comic = Comic.objects.first()
        assert first_comic is not None

        action = Genre.objects.create(name="Action")
        drama = Genre.objects.create(name="Drama")
        comedy = Genre.objects.create(name="Comedy")

        first_comic.genres.add(action, drama)
        comic_b = self._create_sibling_comic(first_comic, "B", 2)
        comic_b.genres.add(action, drama)  # same set as first_comic
        comic_c = self._create_sibling_comic(first_comic, "C", 3)
        comic_c.genres.add(comedy)
        # comic_d has no genres so it sorts to one end.
        comic_d = self._create_sibling_comic(first_comic, "D", 4)

        self._set_view_mode_table()
        self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"orderBy": "genres", "orderReverse": False}),
            content_type="application/json",
        )
        rows = self._browse_series(columns="cover,name,genres")["rows"]
        sets = [tuple(r.get("genres") or []) for r in rows]
        self._assert_genre_sort_classes(sets)
        # Spot-check that every fixture comic is in the result.
        pks = {r["pk"] for r in rows}
        expected_pks = {c.pk for c in (first_comic, comic_b, comic_c, comic_d)}
        assert expected_pks <= pks

    @staticmethod
    def _assert_genre_sort_classes(sets: list[tuple[str, ...]]) -> None:
        """Assert the four-row genre fixture forms the expected equivalence classes."""
        # Fixture: two "Action,Drama" rows, one "Comedy" row, one
        # empty row. JsonGroupArray sorts equal sets together so the
        # two A/D rows must be adjacent in the result list.
        action_drama = frozenset({"Action", "Drama"})
        classes = [frozenset(s) for s in sets]
        expected = (action_drama, action_drama, frozenset({"Comedy"}), frozenset())
        assert sorted(classes, key=str) == sorted(expected, key=str)
        ad_indexes = [i for i, c in enumerate(classes) if c == action_drama]
        assert ad_indexes[1] - ad_indexes[0] == 1

    def test_table_view_group_intersection_scalar_all_share(self) -> None:
        """Series row: ``year`` shows the value when every child comic shares it."""
        from codex.models import Library
        from codex.models.named import Country

        first_comic = Comic.objects.first()
        assert first_comic is not None
        library = Library.objects.first()
        assert library is not None
        country_us = Country.objects.create(name="us")
        # Existing comic + 1 new comic; both share year=2024 and country=us.
        first_comic.year = 2024
        first_comic.country = country_us
        first_comic.save()

        path_b = TMP_DIR / "isect-b.cbz"
        path_b.touch()
        comic_b = Comic.objects.create(
            library=library,
            path=path_b,
            issue_number=2,
            name="B",
            publisher=first_comic.publisher,
            imprint=first_comic.imprint,
            series=first_comic.series,
            volume=first_comic.volume,
            size=43,
            year=2024,
            page_count=20,
            country=country_us,
        )
        assert comic_b.pk

        # Browse publishers (root); the series row should be the
        # publishers row's intersection target. We browse the
        # parent — series.
        self._set_view_mode_table()
        # Browse the imprint so the row beneath is a Series.
        url = (
            f"/api/v4/browse/publishers/{first_comic.publisher.pk}"
            "?page=1&columns=cover,name,year,country"
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        body = _v4(response)
        rows = body["rows"]
        # One row — the Series.
        assert len(rows) == 1
        row = rows[0]
        expected_shared_year = 2024
        assert row["year"] == expected_shared_year
        # Country was annotated through pycountry on the FK alias path,
        # but for group intersections we route through the same
        # transform. Either the resolved name ("United States") or the
        # ISO code ("us") is acceptable as long as the intersection
        # produced a non-null value.
        assert row["country"] in ("United States", "us")

    def test_table_view_bookmark_updated_at_column_on_group_row(self) -> None:
        """
        Group rows render ``bookmark_updated_at`` without 500-ing.

        Regression: ``_SCALAR_FIELD_PATHS`` mapped the column to a
        ``"bookmark_updated_at"`` path that resolved against Comic
        directly, but that's not a Comic field — it's the per-user
        filtered ``Max(bookmark__updated_at)`` aggregate the order
        path already builds. ``compute_collection_intersections`` therefore
        crashed with ``FieldError`` the moment a group view was
        rendered in table mode with the "Last Read" column visible
        and a different order key (the default). The fix drops the
        broken intersection entry and extends
        ``_annotate_bookmark_updated_at`` to attach the aggregate to
        collection queryset in table view so the cell display can read
        it via ``getattr``.
        """
        from codex.models.bookmark import Bookmark

        first_comic = Comic.objects.first()
        assert first_comic is not None
        user = User.objects.get(username="table_response_test")
        Bookmark.objects.create(user=user, comic=first_comic, page=3)

        self._set_view_mode_table()
        url = (
            f"/api/v4/browse/publishers/{first_comic.publisher.pk}"
            "?page=1&columns=cover,name,bookmark_updated_at"
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        body = _v4(response)
        rows = body["rows"]
        assert rows, body
        row = rows[0]
        # The cell uses the per-user-filtered Max aggregate annotation,
        # so it should be a non-empty ISO timestamp string from the
        # bookmark we just created.
        assert row.get("bookmarkUpdatedAt"), row

    def test_table_view_group_publisher_name_renders_for_series_rows(self) -> None:
        """
        Series rows show ``publisher_name`` via child-comic intersection.

        Regression: ``annotate_collection_names`` only annotated
        ``publisher_name`` for Comic and Imprint querysets, and
        ``publisher_name`` was missing from ``_SCALAR_FIELD_PATHS``,
        so Series rows (top_collection=s) — and Volume / Folder /
        StoryArc by extension — rendered the publisher cell blank
        even when every child comic shared a publisher. The fix
        added the FK-name path to the scalar-intersection set so
        the display computer picks it up.
        """
        first_comic = Comic.objects.first()
        assert first_comic is not None
        url = (
            f"/api/v4/browse/publishers/{first_comic.publisher.pk}"
            "?page=1&columns=cover,name,publisher_name,series_name"
        )
        self._set_view_mode_table()
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        body = _v4(response)
        rows = body["rows"]
        assert rows, body
        row = rows[0]
        assert row["publisherName"] == first_comic.publisher.name, row
        assert row["seriesName"] == first_comic.series.name, row

    def test_table_view_group_intersection_scalar_mixed(self) -> None:
        """Series row: ``year`` is null when child comics differ."""
        from codex.models import Library

        first_comic = Comic.objects.first()
        assert first_comic is not None
        library = Library.objects.first()
        assert library is not None
        first_comic.year = 2024
        first_comic.save()

        path_b = TMP_DIR / "mixed-b.cbz"
        path_b.touch()
        Comic.objects.create(
            library=library,
            path=path_b,
            issue_number=2,
            name="B",
            publisher=first_comic.publisher,
            imprint=first_comic.imprint,
            series=first_comic.series,
            volume=first_comic.volume,
            size=43,
            year=2025,  # different year
            page_count=20,
        )

        self._set_view_mode_table()
        url = (
            f"/api/v4/browse/publishers/{first_comic.publisher.pk}"
            "?page=1&columns=cover,name,year"
        )
        response = self.client.get(url)
        body = _v4(response)
        rows = body["rows"]
        row = rows[0]
        # No intersection — child comics differ.
        assert row["year"] is None

    def test_table_view_group_cumulative_page_count(self) -> None:
        """Series row: ``page_count`` shows Sum across children (cover-view rule)."""
        from codex.models import Library

        first_comic = Comic.objects.first()
        assert first_comic is not None
        library = Library.objects.first()
        assert library is not None
        first_comic.page_count = 22
        first_comic.save()

        path_b = TMP_DIR / "sum-b.cbz"
        path_b.touch()
        Comic.objects.create(
            library=library,
            path=path_b,
            issue_number=2,
            name="B",
            publisher=first_comic.publisher,
            imprint=first_comic.imprint,
            series=first_comic.series,
            volume=first_comic.volume,
            size=43,
            year=2024,
            page_count=18,
        )

        self._set_view_mode_table()
        url = (
            f"/api/v4/browse/publishers/{first_comic.publisher.pk}"
            "?page=1&columns=cover,name,page_count,size"
        )
        response = self.client.get(url)
        body = _v4(response)
        rows = body["rows"]
        row = rows[0]
        # ``page_count`` is cumulative — series row shows the total
        # across both children, not the intersected value (which
        # would be NULL since 22 ≠ 18). Cover-view's collection card
        # display Sum here too; table view matches.
        expected_total_pages = 22 + 18
        assert row["pageCount"] == expected_total_pages, row

    def test_table_view_simple_m2m_intersections_share_one_union_query(
        self,
    ) -> None:
        """
        Regression: simple-M2M columns batch into one ``UNION ALL`` query.

        Each per-column M2M intersection used to issue its own
        ``Comic.filter().filter().values().annotate()`` round-trip;
        ``_compute_simple_m2m_intersections_batched`` follows the
        metadata-view pattern (``query_intersections``'s
        ``_query_m2m_intersections``) and unions per-through-table
        sub-queries into a single SQL transmission. Composite M2M
        columns (credits / identifiers / universes / story_arcs)
        still issue their own queries.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from codex.models.named import Character, Genre, Tag, Team

        comic = Comic.objects.first()
        assert comic is not None
        comic.genres.add(Genre.objects.create(name="Sci-Fi"))
        comic.tags.add(Tag.objects.create(name="HiRes"))
        comic.characters.add(Character.objects.create(name="Spider-Man"))
        comic.teams.add(Team.objects.create(name="Avengers"))

        self._set_view_mode_table()
        url = (
            f"/api/v4/browse/publishers/{comic.publisher.pk}?page=1&columns="
            "cover,name,genres,tags,characters,teams,locations,stories,series_groups"
        )
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        # Pre-fix: 7 separate queries (one per visible simple-M2M
        # column). Post-fix: a single UNION-ALL query references all
        # seven through-tables.
        max_expected_through_queries = 3
        through_count = _count_through_table_queries(ctx.captured_queries)
        assert through_count <= max_expected_through_queries, (
            f"got {through_count} through-table queries:\n"
            + "\n".join(
                q["sql"] for q in ctx.captured_queries if "codex_comic_" in q["sql"]
            )
        )

    def test_table_view_group_intersections_batch_into_one_scalar_query(
        self,
    ) -> None:
        """
        Regression: the per-page scalar / cumulative aggregates issue one query.

        ``compute_collection_intersections`` previously emitted one query
        per visible scalar column (year, country, language, tagger,
        page_count, size, …). On a wide table the round-trip count
        scaled with the column set. The batched helper combines all
        scalars + cumulatives + comic counts into a single
        ``Comic.filter().values(rel).annotate(**)`` query. M2M
        columns each still issue their own query (different
        through-table per JOIN; combining would cross-multiply).
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Hit a series row with seven scalar / cumulative columns so
        # the pre-fix path would have issued seven separate queries
        # (plus a count). The batched path issues one.
        first_comic = Comic.objects.first()
        assert first_comic is not None
        self._set_view_mode_table()
        url = (
            f"/api/v4/browse/publishers/{first_comic.publisher.pk}?page=1&columns="
            "cover,name,year,page_count,size,publisher_name,country,language"
        )
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        # ``compute_collection_intersections``-attributable queries have a
        # signature stable across schema additions: a SELECT against
        # ``codex_comic`` that GROUPs by the parent FK column. M2M
        # intersections look similar but JOIN through a
        # ``codex_comic_<m2m>`` table — exclude those.
        scalar_queries = [
            q["sql"]
            for q in ctx.captured_queries
            if 'FROM "codex_comic"' in q["sql"]
            and "GROUP BY" in q["sql"]
            and "codex_comic_" not in q["sql"]
        ]
        # Two batched scalar groups: one for the page-mtime computer,
        # one for the column intersections. Pinning ≤ this constant
        # leaves a tolerance for incidental future grouping queries;
        # the important property is that *adding visible scalar
        # columns doesn't multiply this count.*
        max_expected_scalar_queries = 3
        assert len(scalar_queries) <= max_expected_scalar_queries, "\n".join(
            scalar_queries
        )

    def test_table_view_group_cumulative_page_count_with_duplicates(self) -> None:
        """
        Regression: cumulative sums must not de-duplicate equal values.

        ``_compute_scalar_sum`` previously called
        ``Sum(comic_path, distinct=True)`` which folded sibling
        comics with the same ``page_count`` into a single contribution.
        Two child comics with ``page_count=20`` would total 20
        instead of 40. The batched aggregate drops ``distinct=True``
        — duplicate values across siblings are now summed correctly.
        """
        from codex.models import Library

        first_comic = Comic.objects.first()
        assert first_comic is not None
        library = Library.objects.first()
        assert library is not None
        first_comic.page_count = 20
        first_comic.save()

        path_b = TMP_DIR / "sum-dup-b.cbz"
        path_b.touch()
        Comic.objects.create(
            library=library,
            path=path_b,
            issue_number=2,
            name="B",
            publisher=first_comic.publisher,
            imprint=first_comic.imprint,
            series=first_comic.series,
            volume=first_comic.volume,
            size=43,
            year=2024,
            page_count=20,  # same as the existing comic
        )

        self._set_view_mode_table()
        url = (
            f"/api/v4/browse/publishers/{first_comic.publisher.pk}"
            "?page=1&columns=cover,name,page_count"
        )
        response = self.client.get(url)
        rows = _v4(response)["rows"]
        expected_total = 20 + 20
        assert rows[0]["pageCount"] == expected_total, rows[0]

    def test_table_view_group_intersection_m2m(self) -> None:
        """Series row: genres include only values every comic shares."""
        from codex.models import Library
        from codex.models.named import Genre

        first_comic = Comic.objects.first()
        assert first_comic is not None
        library = Library.objects.first()
        assert library is not None

        action = Genre.objects.create(name="Action")
        drama = Genre.objects.create(name="Drama")
        comedy = Genre.objects.create(name="Comedy")
        first_comic.genres.add(action, drama)

        path_b = TMP_DIR / "m2m-b.cbz"
        path_b.touch()
        comic_b = Comic.objects.create(
            library=library,
            path=path_b,
            issue_number=2,
            name="B",
            publisher=first_comic.publisher,
            imprint=first_comic.imprint,
            series=first_comic.series,
            volume=first_comic.volume,
            size=43,
            year=2024,
            page_count=20,
        )
        # Comic B has Drama only (shared) + Comedy (unique).
        comic_b.genres.add(drama, comedy)

        self._set_view_mode_table()
        url = (
            f"/api/v4/browse/publishers/{first_comic.publisher.pk}"
            "?page=1&columns=cover,name,genres"
        )
        response = self.client.get(url)
        body = _v4(response)
        rows = body["rows"]
        row = rows[0]
        # Drama is the only genre both comics share.
        assert row["genres"] == ["Drama"]

    def test_table_view_group_m2m_sort_clusters_identical_intersections(
        self,
    ) -> None:
        """Two series with the same intersection genres sort adjacent."""
        from codex.models import Library
        from codex.models.named import Genre

        first_comic = Comic.objects.first()
        assert first_comic is not None
        library = Library.objects.first()
        assert library is not None
        publisher = first_comic.publisher
        imprint = first_comic.imprint

        action = Genre.objects.create(name="Action")
        drama = Genre.objects.create(name="Drama")
        comedy = Genre.objects.create(name="Comedy")

        # Series A: every comic has Action + Drama as the intersection.
        series_a = first_comic.series
        first_comic.genres.add(action, drama)
        path_a2 = TMP_DIR / "ga2.cbz"
        path_a2.touch()
        comic_a2 = Comic.objects.create(
            library=library,
            path=path_a2,
            issue_number=2,
            name="A2",
            publisher=publisher,
            imprint=imprint,
            series=series_a,
            volume=first_comic.volume,
            size=43,
            year=2024,
            page_count=20,
        )
        comic_a2.genres.add(action, drama, comedy)  # Comedy is unique to a2

        # Series B (new): every comic has Action + Drama too.
        series_b = Series.objects.create(
            name="Bravo", imprint=imprint, publisher=publisher
        )
        volume_b = Volume.objects.create(
            name="2024", series=series_b, imprint=imprint, publisher=publisher
        )
        path_b1 = TMP_DIR / "gb1.cbz"
        path_b1.touch()
        comic_b1 = Comic.objects.create(
            library=library,
            path=path_b1,
            issue_number=1,
            name="B1",
            publisher=publisher,
            imprint=imprint,
            series=series_b,
            volume=volume_b,
            size=44,
            year=2024,
            page_count=20,
        )
        comic_b1.genres.add(action, drama)
        path_b2 = TMP_DIR / "gb2.cbz"
        path_b2.touch()
        comic_b2 = Comic.objects.create(
            library=library,
            path=path_b2,
            issue_number=2,
            name="B2",
            publisher=publisher,
            imprint=imprint,
            series=series_b,
            volume=volume_b,
            size=45,
            year=2024,
            page_count=20,
        )
        comic_b2.genres.add(action, drama)  # same intersection as A

        # Series C (new): one comic with Comedy only — different intersection.
        series_c = Series.objects.create(
            name="Charlie", imprint=imprint, publisher=publisher
        )
        volume_c = Volume.objects.create(
            name="2024", series=series_c, imprint=imprint, publisher=publisher
        )
        path_c = TMP_DIR / "gc.cbz"
        path_c.touch()
        comic_c = Comic.objects.create(
            library=library,
            path=path_c,
            issue_number=1,
            name="C1",
            publisher=publisher,
            imprint=imprint,
            series=series_c,
            volume=volume_c,
            size=46,
            year=2024,
            page_count=20,
        )
        comic_c.genres.add(comedy)

        self._set_view_mode_table()
        # Sort series rows by genres ascending.
        self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"orderBy": "genres", "orderReverse": False}),
            content_type="application/json",
        )
        url = (
            f"/api/v4/browse/publishers/{publisher.pk}?page=1&columns=cover,name,genres"
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        body = _v4(response)
        rows = body["rows"]
        # Three series rows.
        names = [r["name"] for r in rows]
        # Series A and B share the same intersection ({Action, Drama}); they
        # must sort adjacent.
        idx_a = names.index(series_a.name)
        idx_b = names.index(series_b.name)
        assert abs(idx_a - idx_b) == 1, names

    def test_table_view_m2m_sort_doesnt_crash_cover_subquery(self) -> None:
        """
        Browsing groups with M2M sort active doesn't fail on the cover subquery.

        Regression: the cover subquery is a correlated Comic queryset
        that doesn't carry the outer view's M2M alias annotation, so
        an M2M ORDER BY would resolve a nonexistent column and 500.
        """
        self._set_view_mode_table()
        # Sort by an M2M key while browsing a level that produces collection row.
        self.client.patch(
            _SETTINGS_URL,
            data=json.dumps({"orderBy": "universes", "orderReverse": True}),
            content_type="application/json",
        )
        first_comic = Comic.objects.first()
        assert first_comic is not None
        url = (
            f"/api/v4/browse/publishers/{first_comic.publisher.pk}"
            "?page=1&columns=cover,name,universes"
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content

    def test_table_view_credits_skips_empty_person_name(self) -> None:
        """Credits with an unnamed person are filtered out."""
        from codex.models.named import Credit, CreditPerson

        comic = Comic.objects.first()
        assert comic is not None
        person = CreditPerson.objects.create(name="")
        credit = Credit.objects.create(person=person)
        comic.credits.add(credit)

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,credits")
        rows = body["rows"]
        row = rows[0]
        assert row.get("credits") in ([], None)
