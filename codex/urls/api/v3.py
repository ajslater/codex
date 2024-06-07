"""codex:api:v3 URL Configuration."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from codex.views.browser.mtime import MtimeView
from codex.views.opds.urls import OPDSURLsView
from codex.views.version import VersionView

app_name = "v3"
urlpatterns = [
    path("auth/", include("codex.urls.api.auth")),
    # reader must come first to occlude browser group
    path("c/", include("codex.urls.api.reader")),
    path("<group:group>/", include("codex.urls.api.browser")),
    path("mtime", MtimeView.as_view(), name="mtimes"),
    path("version", VersionView.as_view(), name="version"),
    path("admin/", include("codex.urls.api.admin")),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("opds-urls", OPDSURLsView.as_view(), name="opds_urls"),
    path(
        "",
        SpectacularSwaggerView.as_view(url_name="api:v3:schema"),
        name="base",
    ),
]
