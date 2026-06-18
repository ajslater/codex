"""
codex:api:v4 URL Configuration.

Mounted at ``/api/v4/`` conditionally by ``codex.urls.api.root`` when
``FEATURES.api_v4`` is on. Each phase of ``tasks/api-v4.md`` lights up
another include block here.
"""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from codex.views.browser.cover import cover_dispatch_by_source
from codex.views.browser.mtime import MtimeView
from codex.views.opds.urls import OPDSURLsView
from codex.views.session import SessionView
from codex.views.version import VersionView

app_name = "v4"
urlpatterns = [
    path("admin/", include("codex.urls.api.v4.admin")),
    path("auth/", include("codex.urls.api.v4.auth")),
    path("browse/", include("codex.urls.api.v4.browse")),
    path("comics/", include("codex.urls.api.v4.comics")),
    path("favorites/", include("codex.urls.api.v4.favorites")),
    path("reader/", include("codex.urls.api.v4.reader")),
    path("mtime", MtimeView.as_view(), name="mtime"),
    path("session", SessionView.as_view(), name="session"),
    path("version", VersionView.as_view(), name="version"),
    path("opds-urls", OPDSURLsView.as_view(), name="opds_urls"),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("covers/<str:source>/<int:pk>", cover_dispatch_by_source, name="covers"),
]
