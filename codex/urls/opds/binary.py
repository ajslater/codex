"""codex:opds:v1 URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_control, cache_page
from django.views.decorators.vary import vary_on_headers

from codex.urls.const import COVER_MAX_AGE, PAGE_MAX_AGE
from codex.views.opds.binary import (
    OPDSCoverView,
    OPDSCustomCoverView,
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
    # Per-pk covers.
    path(
        "c/<int:pk>/cover.webp",
        # OPDS accepts Basic, Bearer, and Session auth. Vary on both
        # Cookie and Authorization so cached responses don't leak across
        # auth types or users.  See codex.urls.api.reader "cover" route
        # for the full rationale on the cache_page composition.
        cache_page(COVER_MAX_AGE)(
            cache_control(max_age=COVER_MAX_AGE, public=True)(
                vary_on_headers("Cookie", "Authorization")(OPDSCoverView.as_view())
            )
        ),
        name="cover",
    ),
    path(
        "custom_cover/<int:pk>/cover.webp",
        cache_page(COVER_MAX_AGE)(
            cache_control(max_age=COVER_MAX_AGE, public=True)(
                vary_on_headers("Cookie", "Authorization")(
                    OPDSCustomCoverView.as_view()
                )
            )
        ),
        name="custom_cover",
    ),
    path(
        "c/<int:pk>/download/<str:filename>",
        OPDSDownloadView.as_view(),
        name="download",
    ),
]
