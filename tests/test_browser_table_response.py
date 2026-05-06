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

    def test_cover_view_returns_books_not_rows(self) -> None:
        # Default view_mode is cover; the response must have books, not rows.
        body = self._browse_series()
        assert "books" in body
        assert "rows" not in body

    def test_table_view_returns_rows(self) -> None:
        self._set_view_mode_table()
        body = self._browse_series(columns="cover,name,issue_number")
        assert "rows" in body
        assert "books" not in body
        assert "groups" not in body
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
