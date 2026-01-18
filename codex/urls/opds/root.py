"""codex:opds URL Configuration."""

from django.urls import include, path, re_path

from codex.views.opds.util import full_redirect_view

app_name = "opds"

opds_v1_start_view = full_redirect_view("opds:v1:start")
opds_v2_start_view = full_redirect_view("opds:v2:start")
auth_v1_view = full_redirect_view("opds:auth:v1")

urlpatterns = (
    path(
        "auth/",
        include("codex.urls.opds.authentication"),
        name="auth",
    ),
    path("auth", auth_v1_view),
    path("bin/", include("codex.urls.opds.binary")),
    path("v1.2/", include("codex.urls.opds.v1")),
    re_path(r"v1\..*", opds_v1_start_view),
    path("v2.0/", include("codex.urls.opds.v2")),
    re_path(r"v2\..*", opds_v2_start_view),
    re_path(".*", opds_v1_start_view),
)
