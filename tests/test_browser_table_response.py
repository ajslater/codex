"""End-to-end tests for the table-view response shape."""

import json
import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.serializers.browser.settings import BrowserPageInputSerializer
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_BAD_REQUEST: Final = 400
TMP_DIR = Path("/tmp/codex.tests.browser_table_response")  # noqa: S108


class BrowserPageInputColumnsTestCase(TestCase):
    """Validate the ``columns=`` query-param parser."""

    def test_empty_returns_empty_tuple(self):
        s = BrowserPageInputSerializer(data={"columns": ""})
        assert s.is_valid(), s.errors
        assert s.validated_data["columns"] == ()

    def test_csv_parsed_to_tuple(self):
        s = BrowserPageInputSerializer(data={"columns": "cover,name,issue"})
        assert s.is_valid(), s.errors
        assert s.validated_data["columns"] == ("cover", "name", "issue")

    def test_whitespace_trimmed(self):
        s = BrowserPageInputSerializer(data={"columns": " cover , name "})
        assert s.is_valid(), s.errors
        assert s.validated_data["columns"] == ("cover", "name")

    def test_unknown_key_rejected(self):
        s = BrowserPageInputSerializer(data={"columns": "cover,phantom_column"})
        assert not s.is_valid()
        assert "columns" in s.errors


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
            "/api/v3/r/settings",
            data=json.dumps({"viewMode": "table"}),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _browse_series(self, *, columns: str | None = None) -> dict:
        url = f"/api/v3/s/{self.series.pk}/1"
        if columns is not None:
            url = f"{url}?columns={columns}"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return response.json()

    def test_cover_view_returns_cards_with_empty_rows(self) -> None:
        """Cover mode: ``rows`` is present but empty; cards are populated."""
        body = self._browse_series()
        assert "books" in body
        # ``rows`` is always emitted by the unified serializer for client
        # round-tripping; in cover mode it's just an empty list.
        assert body.get("rows") == []

    def test_table_view_returns_rows_alongside_cards(self) -> None:
        """Table mode: both ``rows`` (table) and cards (mobile fallback)."""
        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,issue")
        # Cards stay populated so the mobile auto-fallback can use them
        # without a second round-trip.
        assert "books" in body
        rows = body["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert "pk" in row
        assert "coverPk" in row  # camelCased
        assert "name" in row
        # ``issue`` is the compound column (issue_number + issue_suffix).
        assert "issue" in row

    def test_table_view_invalid_columns_rejected(self) -> None:
        self._set_view_mode_table()
        url = f"/api/v3/s/{self.series.pk}/1?columns=cover,phantom_column"
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
        from codex.models import Library
        from codex.models.named import Genre

        # Two comics in the same series sharing identical genre sets.
        # Sorting by genres should place them adjacent. A third comic
        # with a different genre set goes elsewhere; a fourth with no
        # genres should sort to one end.
        first_comic = Comic.objects.first()
        assert first_comic is not None
        library = Library.objects.first()
        assert library is not None
        publisher = first_comic.publisher
        imprint = first_comic.imprint
        series = first_comic.series
        volume = first_comic.volume

        action = Genre.objects.create(name="Action")
        drama = Genre.objects.create(name="Drama")
        comedy = Genre.objects.create(name="Comedy")

        first_comic.genres.add(action, drama)

        path_b = TMP_DIR / "b.cbz"
        path_b.touch()
        comic_b = Comic.objects.create(
            library=library,
            path=path_b,
            issue_number=2,
            name="B",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=43,
            year=2024,
            page_count=20,
        )
        comic_b.genres.add(action, drama)  # same set as first_comic
        path_c = TMP_DIR / "c.cbz"
        path_c.touch()
        comic_c = Comic.objects.create(
            library=library,
            path=path_c,
            issue_number=3,
            name="C",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=44,
            year=2024,
            page_count=20,
        )
        comic_c.genres.add(comedy)
        path_d = TMP_DIR / "d.cbz"
        path_d.touch()
        comic_d = Comic.objects.create(
            library=library,
            path=path_d,
            issue_number=4,
            name="D",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=45,
            year=2024,
            page_count=20,
        )
        # comic_d has no genres

        self._set_view_mode_table()
        # Sort by genres ascending.
        self.client.patch(
            "/api/v3/r/settings",
            data=json.dumps({"orderBy": "genres", "orderReverse": False}),
            content_type="application/json",
        )
        body = self._browse_series(columns="cover,name,genres")
        rows = body["rows"]
        expected_row_count = 4
        assert len(rows) == expected_row_count
        # Group rows by their genre set (after the JsonGroupArray sort).
        sets = [tuple(r.get("genres") or []) for r in rows]
        # The two "Action,Drama" rows should be adjacent.
        action_drama_indexes = [
            i for i, s in enumerate(sets) if set(s) == {"Action", "Drama"}
        ]
        expected_action_drama = 2
        assert len(action_drama_indexes) == expected_action_drama
        assert action_drama_indexes[1] - action_drama_indexes[0] == 1
        # No-genres comic appears once (empty list / null).
        empty_indexes = [i for i, s in enumerate(sets) if not s]
        assert len(empty_indexes) == 1
        # Verify the unique-genre-set comic appears once.
        comedy_indexes = [i for i, s in enumerate(sets) if set(s) == {"Comedy"}]
        assert len(comedy_indexes) == 1
        # comic_b/comic_c/comic_d existed by id; spot-check pks.
        pks = [r["pk"] for r in rows]
        for c in (first_comic, comic_b, comic_c, comic_d):
            assert c.pk in pks

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
        url = f"/api/v3/p/{first_comic.publisher.pk}/1?columns=cover,name,year,country"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        body = response.json()
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
        url = f"/api/v3/p/{first_comic.publisher.pk}/1?columns=cover,name,year"
        response = self.client.get(url)
        body = response.json()
        rows = body["rows"]
        row = rows[0]
        # No intersection — child comics differ.
        assert row["year"] is None

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
        url = f"/api/v3/p/{first_comic.publisher.pk}/1?columns=cover,name,genres"
        response = self.client.get(url)
        body = response.json()
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
            "/api/v3/r/settings",
            data=json.dumps({"orderBy": "genres", "orderReverse": False}),
            content_type="application/json",
        )
        url = f"/api/v3/p/{publisher.pk}/1?columns=cover,name,genres"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        body = response.json()
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
        # Sort by an M2M key while browsing a level that produces group rows.
        self.client.patch(
            "/api/v3/r/settings",
            data=json.dumps({"orderBy": "universes", "orderReverse": True}),
            content_type="application/json",
        )
        first_comic = Comic.objects.first()
        assert first_comic is not None
        url = f"/api/v3/p/{first_comic.publisher.pk}/1?columns=cover,name,universes"
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
