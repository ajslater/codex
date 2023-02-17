"""codex:api:v3 URL Configuration."""
from django.urls import include, path, register_converter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from codex.urls.converters import GroupConverter
from codex.views.version import VersionView


register_converter(GroupConverter, "group")


app_name = "v3"
urlpatterns = [
    path("auth/", include("codex.urls.api.auth")),
    # reader must come first to occlude browser group
    path("c/", include("codex.urls.api.reader")),
    path("<group:group>/", include("codex.urls.api.browser")),
    path("version", VersionView.as_view(), name="version"),
    path("admin/", include("codex.urls.api.admin")),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path(
        "",
        SpectacularSwaggerView.as_view(url_name="api:v3:schema"),
        name="base",
    ),
]
