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
        s = BrowserPageInputSerializer(data={"columns": "cover,name,issue_number"})
        assert s.is_valid(), s.errors
        assert s.validated_data["columns"] == ("cover", "name", "issue_number")

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
        body = self._browse_series(columns="cover,name,issue_number")
        # Cards stay populated so the mobile auto-fallback can use them
        # without a second round-trip.
        assert "books" in body
        rows = body["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert "pk" in row
        assert "coverPk" in row  # camelCased
        assert "name" in row
        assert "issueNumber" in row

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
        """FK-name columns (country, language, etc.) carry their values."""
        from codex.models.named import Country, Language

        comic = Comic.objects.first()
        assert comic is not None
        country = Country.objects.create(name="USA")
        language = Language.objects.create(name="en")
        comic.country = country
        comic.language = language
        comic.save()

        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,country,language")
        rows = body["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert row["country"] == "USA"
        assert row["language"] == "en"

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
