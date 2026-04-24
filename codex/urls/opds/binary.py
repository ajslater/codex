"""codex:opds:v1 URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_control

from codex.urls.const import COVER_MAX_AGE, PAGE_MAX_AGE
from codex.views.opds.binary import (
    OPDSComicCoverByPkView,
    OPDSCoverView,
    OPDSCustomCoverByPkView,
    OPDSDownloadView,
    OPDSPageView,
)

app_name = "bin"


urlpatterns = [
    #
    # Reader
    path(
        "c/<int:pk>/<int:page>/page.jpg",
        cache_control(max_age=PAGE_MAX_AGE, public=True)(OPDSPageView.as_view()),
        name="page",
    ),
    #
    # Per-pk thin covers — OPDS feeds emit these when the browser pipeline
    # pre-resolved a cover pk; collapses the pipeline-per-cover fan-out.
    path(
        "c/<int:pk>/cover.webp",
        cache_control(max_age=COVER_MAX_AGE, public=True)(
            OPDSComicCoverByPkView.as_view()
        ),
        name="cover_by_pk",
    ),
    path(
        "custom_cover/<int:pk>/cover.webp",
        cache_control(max_age=COVER_MAX_AGE, public=True)(
            OPDSCustomCoverByPkView.as_view()
        ),
        name="custom_cover_by_pk",
    ),
    #
    # utilities
    path(
        "<str:group>/<int_list:pks>/cover.webp",
        cache_control(max_age=COVER_MAX_AGE, public=True)(OPDSCoverView.as_view()),
        name="cover",
    ),
    path(
        "c/<int:pk>/download/<str:filename>",
        OPDSDownloadView.as_view(),
        name="download",
    ),
]
