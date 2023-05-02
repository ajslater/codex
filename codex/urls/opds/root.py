"""codex:opds URL Configuration."""
from django.urls import include, path, re_path

from codex.views.opds.v1.start import opds_1_start_view
from codex.views.opds.v2.start import opds_2_start_view

app_name = "opds"

urlpatterns = [
    path(
        "authentication",
        include("codex.urls.opds.authentication"),
        name="authentication",
    ),
    path("bin/", include("codex.urls.opds.binary")),
    path("v1.2/", include("codex.urls.opds.v1")),
    path("v1/", opds_1_start_view, name="v1_start"),
    path("v2.0/", include("codex.urls.opds.v2")),
    path("v2/", opds_2_start_view, name="v2_start"),
    path("", opds_1_start_view, name="start"),
    re_path(".*", opds_1_start_view, name="not_found"),
]
