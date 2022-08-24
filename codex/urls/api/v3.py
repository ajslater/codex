"""codex:api:v3 URL Configuration."""
from django.urls import include, path
from django.views.decorators.cache import cache_control
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from codex.views.version import VersionView


VERSIONS_AGE = 60 * 60 * 12


app_name = "v3"
urlpatterns = [
    path("c/", include("codex.urls.api.reader")),
    path("auth/", include("codex.urls.api.auth")),
    path("admin/", include("codex.urls.api.admin")),
    path("<str:group>/", include("codex.urls.api.browser")),
    path(
        "version",
        cache_control(max_age=VERSIONS_AGE)(VersionView.as_view()),
        name="version",
    ),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path(
        "",
        SpectacularSwaggerView.as_view(url_name="api:v3:schema"),
        name="base",
    ),
]
