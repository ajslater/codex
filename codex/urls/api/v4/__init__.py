"""
codex:api:v4 URL Configuration.

Mounted at ``/api/v4/`` conditionally by ``codex.urls.api.root`` when
``FEATURES.api_v4`` is on. Each phase of ``tasks/api-v4.md`` lights up
another include block here.
"""

from django.urls import include, path

from codex.views.v4.session import V4SessionView
from codex.views.v4.version import V4VersionView

app_name = "v4"
urlpatterns = [
    path("auth/", include("codex.urls.api.v4.auth")),
    path("browse/", include("codex.urls.api.v4.browse")),
    path("comics/", include("codex.urls.api.v4.comics")),
    path("reader/", include("codex.urls.api.v4.reader")),
    path("session", V4SessionView.as_view(), name="session"),
    path("version", V4VersionView.as_view(), name="version"),
]
