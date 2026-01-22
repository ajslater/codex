"""codex:opds URL Configuration."""

from django.urls import include, path, re_path
from django.views.generic.base import RedirectView

app_name = "opds"

urlpatterns = (
    path(
        "auth/",
        include("codex.urls.opds.authentication"),
        name="auth",
    ),
    re_path("auth.*", RedirectView.as_view(pattern_name="opds:auth:v1")),
    path("bin/", include("codex.urls.opds.binary")),
    path("v1.2/", include("codex.urls.opds.v1")),
    path("v2.0/", include("codex.urls.opds.v2")),
    re_path(r"v?2[\.\d].*", RedirectView.as_view(pattern_name="opds:v2:start")),
    re_path(".*", RedirectView.as_view(pattern_name="opds:v1:start")),
)
