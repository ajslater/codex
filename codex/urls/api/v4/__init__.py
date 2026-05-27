"""
codex:api:v4 URL Configuration.

Mounted at ``/api/v4/`` conditionally by ``codex.urls.api.root`` when
``FEATURES.api_v4`` is on. Each phase of ``tasks/api-v4.md`` lights up
another include block here.
"""

from django.urls import include, path

from codex.views.v4.session import V4SessionView
from codex.views.v4.utility import (
    V4OPDSURLsView,
    V4SchemaView,
    v4_cover_dispatch,
)
from codex.views.v4.version import V4VersionView

app_name = "v4"
urlpatterns = [
    path("admin/", include("codex.urls.api.v4.admin")),
    path("auth/", include("codex.urls.api.v4.auth")),
    path("browse/", include("codex.urls.api.v4.browse")),
    path("comics/", include("codex.urls.api.v4.comics")),
    path("favorites/", include("codex.urls.api.v4.favorites")),
    path("reader/", include("codex.urls.api.v4.reader")),
    path("session", V4SessionView.as_view(), name="session"),
    path("version", V4VersionView.as_view(), name="version"),
    path("opds-urls", V4OPDSURLsView.as_view(), name="opds_urls"),
    path("schema", V4SchemaView.as_view(), name="schema"),
    path("covers/<str:source>/<int:pk>", v4_cover_dispatch, name="covers"),
]
