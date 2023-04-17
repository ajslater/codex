"""codex:opds URL Configuration."""
from django.urls import include, path, re_path

from codex.views.opds_v1.start import opds_1_start_view

app_name = "opds"

urlpatterns = [
    path("v1.2/", include("codex.urls.opds.v1")),
    path("v1/", opds_1_start_view, name="v1_start"),
    path("", opds_1_start_view, name="start"),
    re_path(".*", opds_1_start_view, name="not_found"),
]
