"""codex:api:v3 URL Configuration."""

from django.urls import include, path
from django.views.decorators.cache import cache_control, cache_page
from django.views.decorators.vary import vary_on_cookie
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerSplitView,
)

from codex.urls.const import COVER_MAX_AGE
from codex.views.browser.cover import CustomCoverView
from codex.views.browser.mtime import MtimeView
from codex.views.opds.urls import OPDSURLsView
from codex.views.version import VersionView

app_name = "v3"
urlpatterns = [
    path("auth/", include("codex.urls.api.auth")),
    # reader must come first to occlude browser group
    path("c/", include("codex.urls.api.reader")),
    path(
        "custom_cover/<int:pk>/cover.webp",
        # See codex.urls.api.reader "cover" route for rationale on the
        # cache_page + vary_on_cookie composition.
        cache_page(COVER_MAX_AGE)(
            cache_control(max_age=COVER_MAX_AGE, public=True)(
                vary_on_cookie(CustomCoverView.as_view())
            )
        ),
        name="custom_cover",
    ),
    path("<group:group>/", include("codex.urls.api.browser")),
    path("mtime", MtimeView.as_view(), name="mtimes"),
    path("version", VersionView.as_view(), name="version"),
    path("admin/", include("codex.urls.api.admin")),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("opds-urls", OPDSURLsView.as_view(), name="opds_urls"),
    path(
        "",
        SpectacularSwaggerSplitView.as_view(url_name="api:v3:schema"),
        name="base",
    ),
]
