"""codex:opds:v1 URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_control
from django.views.decorators.vary import vary_on_headers

from codex.urls.const import PAGE_MAX_AGE
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
    #
    # No ``cache_page`` — see the codex.urls.api.v4.comics "cover" route for
    # why. The views serve ETag / Last-Modified and set their own
    # ``Cache-Control``. OPDS accepts Basic, Bearer, and Session auth, so vary
    # on both Cookie and Authorization to keep a downstream proxy from leaking
    # responses across auth types or users.
    path(
        "c/<int:pk>/cover.webp",
        vary_on_headers("Cookie", "Authorization")(OPDSCoverView.as_view()),
        name="cover",
    ),
    path(
        "custom_cover/<int:pk>/cover.webp",
        vary_on_headers("Cookie", "Authorization")(OPDSCustomCoverView.as_view()),
        name="custom_cover",
    ),
    path(
        "c/<int:pk>/download/<str:filename>",
        OPDSDownloadView.as_view(),
        name="download",
    ),
]
