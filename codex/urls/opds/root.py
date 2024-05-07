"""codex:opds URL Configuration."""

from django.urls import include, path, re_path

from codex.views.opds.util import full_redirect_view

app_name = "opds"

opds_v1_start_view = full_redirect_view("opds:v1:feed")

urlpatterns = (
    path(
        "authentication/",
        include("codex.urls.opds.authentication"),
        name="authentication",
    ),
    path("bin/", include("codex.urls.opds.binary")),
    path("v1.2/", include("codex.urls.opds.v1")),
    path("v1/", opds_v1_start_view, name="v1_start"),
    path("v2.0/", include("codex.urls.opds.v2")),
    path("v2/", full_redirect_view("opds:v2:feed"), name="v2_start"),
    re_path(".*", opds_v1_start_view, name="catchall"),
)
