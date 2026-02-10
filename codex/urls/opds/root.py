"""codex:opds URL Configuration."""

from django.urls import include, path, re_path
from django.views.generic.base import RedirectView

from codex.views.opds.v2.feed import OPDS2StartView

app_name = "opds"

urlpatterns = (
    path(
        "auth/",
        include("codex.urls.opds.authentication"),
        name="auth",
    ),
    path("bin/", include("codex.urls.opds.binary")),
    path("v1.2/", include("codex.urls.opds.v1")),
    path(
        "v2.0",
        OPDS2StartView.as_view(),
        {"group": "r", "pks": (0,), "page": 1},
        name="start",
    ),
    path("v2.0/", include("codex.urls.opds.v2")),
    re_path(r"auth.*", RedirectView.as_view(pattern_name="opds:auth:v1")),
    re_path(r"v?1[\.\d]*", RedirectView.as_view(pattern_name="opds:v1:start")),
    re_path(r"v?2[\.\d]*", RedirectView.as_view(pattern_name="opds:v2:start")),
    path("", RedirectView.as_view(pattern_name="opds:v1:start")),
)
