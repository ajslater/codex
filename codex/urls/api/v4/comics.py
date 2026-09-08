"""codex:api:v4:comics URL Configuration."""

from django.urls import path
from django.views.decorators.vary import vary_on_cookie

from codex.urls.const import PAGE_MAX_AGE
from codex.views.browser.bookmark import ComicBookmarkView
from codex.views.browser.cover import CoverView
from codex.views.download import DownloadView
from codex.views.reader.page import ReaderPageView
from codex.views.reader.settings import ReaderSettingsView
from codex.views.util import cache_control_2xx

app_name = "comics"
urlpatterns = [
    path(
        "<int:pk>/bookmark",
        ComicBookmarkView.as_view(),
        name="bookmark",
    ),
    path(
        "<int:pk>/reader-settings",
        ReaderSettingsView.as_view(),
        name="reader_settings",
    ),
    path(
        "<int:pk>/pages/<int:page>",
        cache_control_2xx(max_age=PAGE_MAX_AGE, public=True)(ReaderPageView.as_view()),
        name="page",
    ),
    path(
        "<int:pk>/cover",
        # No ``cache_page``: covers are already on disk as webp files, so a
        # server-side copy of the response body duplicated them once per user
        # (the key hashes the ``Vary`` values) and could only be invalidated by
        # clearing the whole cache. The view serves ETag / Last-Modified
        # instead, and sets its own ``Cache-Control``. ``Vary`` still has to be
        # declared here so a downstream proxy keys ACL-gated covers per user.
        vary_on_cookie(CoverView.as_view()),
        name="cover",
    ),
    path(
        "<int:pk>/download/<str:filename>",
        DownloadView.as_view(),
        name="download",
    ),
]
