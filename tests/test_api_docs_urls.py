"""Tests for the drf-spectacular schema & interactive docs routes."""

from typing import Final, override

from django.contrib.auth.models import User
from django.test import TestCase

from codex.settings import SECURE_CSP

_SCHEMA_URL: Final = "/api/v4/schema"
_SWAGGER_URL: Final = "/api/v4/"
_HTTP_OK: Final = 200
_HTTP_FORBIDDEN: Final = 403


class APIDocsPermissionTests(TestCase):
    """The schema and the Swagger UI are admin only."""

    def test_anonymous_denied(self) -> None:
        for url in (_SCHEMA_URL, _SWAGGER_URL):
            assert self.client.get(url).status_code == _HTTP_FORBIDDEN

    def test_non_staff_denied(self) -> None:
        self.client.force_login(User.objects.create_user("reader"))
        for url in (_SCHEMA_URL, _SWAGGER_URL):
            assert self.client.get(url).status_code == _HTTP_FORBIDDEN


class APIDocsUITests(TestCase):
    """The Swagger UI renders and points at the schema route."""

    @override
    def setUp(self) -> None:
        self.client.force_login(User.objects.create_superuser("admin", "", "admin"))

    def test_schema_json(self) -> None:
        response = self.client.get(_SCHEMA_URL, {"format": "json"})
        assert response.status_code == _HTTP_OK
        schema = response.json()
        assert schema["info"]["title"] == "Codex API"
        # The Swagger UI route itself is excluded from the schema.
        assert _SWAGGER_URL not in schema["paths"]

    def test_swagger_html_and_split_script(self) -> None:
        response = self.client.get(_SWAGGER_URL)
        assert response.status_code == _HTTP_OK
        html = response.content.decode()
        assert "swagger-ui" in html
        # Split view: the init javascript is a second same-origin
        # request, never an inline <script>.
        assert f"{_SWAGGER_URL}?script=" in html

        script = self.client.get(_SWAGGER_URL, {"script": ""})
        assert script.status_code == _HTTP_OK
        assert script["Content-Type"].startswith("application/javascript")
        assert _SCHEMA_URL in script.content.decode()


class APIDocsCSPTests(TestCase):
    """Every CDN asset the docs templates request is allowed."""

    def test_docs_scripts_in_script_src_elem(self) -> None:
        # script-src-elem is declared by the pdfs-dist overlay, so it
        # masks script-src for element loads and must list the bundles.
        for directive in ("script-src", "script-src-elem"):
            sources = SECURE_CSP[directive]
            assert any("swagger-ui-bundle.js" in source for source in sources)
            assert any(
                "swagger-ui-standalone-preset.js" in source for source in sources
            )

    def test_swagger_css_allowed(self) -> None:
        assert any("swagger-ui.css" in source for source in SECURE_CSP["style-src"])
