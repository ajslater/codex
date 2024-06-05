"""codex:opds:v1 URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_control

from codex.urls.const import COVER_MAX_AGE, PAGE_MAX_AGE
from codex.views.opds.binary import OPDSCoverView, OPDSDownloadView, OPDSPageView

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
