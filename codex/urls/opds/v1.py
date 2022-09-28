"""codex:opds:v1 URL Configuration."""
from django.urls import path, register_converter
from django.views.decorators.cache import cache_control, cache_page

from codex.urls.converters import GroupConverter
from codex.views.cover import CoverView
from codex.views.download import DownloadView
from codex.views.opds_v1.authentication import AuthenticationView
from codex.views.opds_v1.browser import OPDSBrowserView
from codex.views.opds_v1.opensearch import OpenSearchView
from codex.views.opds_v1.start import opds_start_view
from codex.views.reader.page import ReaderPageView


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
        OPDSBrowserView.as_view(),
        name="browser",
    ),
    #
    # Reader
    path(
        "c/<int:pk>/<int:page>/page.jpg",
        cache_control(max_age=PAGE_MAX_AGE)(ReaderPageView.as_view()),
        name="page",
    ),
    #
    # utilities
    path(
        "c/<int:pk>/cover.webp",
        cache_control(max_age=COVER_MAX_AGE)(CoverView.as_view()),
        name="cover",
    ),
    # Chunky Comc Reader requires a . suffix for download links.
    path("c/<int:pk>/download.cbz", DownloadView.as_view(), name="download"),
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
    path("", opds_start_view, name="start"),
]
