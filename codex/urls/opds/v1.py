"""codex:opds:v1 URL Configuration."""
from django.urls import path, register_converter
from django.views.decorators.cache import cache_control, cache_page

from codex.urls.converters import GroupConverter
from codex.views.opds_v1.authentication import AuthenticationView
from codex.views.opds_v1.binary import OPDS1CoverView, OPDS1DownloadView, OPDS1PageView
from codex.views.opds_v1.browser import OPDS1BrowserView
from codex.views.opds_v1.opensearch import OpenSearchView
from codex.views.opds_v1.start import opds_1_start_view

TIMEOUT = 60 * 60
PAGE_MAX_AGE = 60 * 60 * 24 * 7
COVER_MAX_AGE = PAGE_MAX_AGE

app_name = "v1"

register_converter(GroupConverter, "group")

urlpatterns = [
    #
    # Browser
    path(
        "<group:group>/<int:pk>/<int:page>",
        OPDS1BrowserView.as_view(),
        name="browser",
    ),
    #
    # Reader
    path(
        "c/<int:pk>/<int:page>/page.jpg",
        cache_control(max_age=PAGE_MAX_AGE, public=True)(OPDS1PageView.as_view()),
        name="page",
    ),
    #
    # utilities
    path(
        "c/<int:pk>/cover.webp",
        cache_control(max_age=COVER_MAX_AGE, public=True)(OPDS1CoverView.as_view()),
        name="cover",
    ),
    # Chunky Comc Reader requires a full filename for download links.
    path(
        "c/<int:pk>/download/<str:filename>",
        OPDS1DownloadView.as_view(),
        name="download",
    ),
    #
    # definition documents
    path(
        "opensearch",
        cache_page(TIMEOUT)(OpenSearchView.as_view()),
        name="opensearch",
    ),
    path(
        "authentication",
        cache_page(TIMEOUT)(AuthenticationView.as_view()),
        name="authentication",
    ),
    path("", opds_1_start_view, name="start"),
]
