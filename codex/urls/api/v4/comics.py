"""codex:api:v4:comics URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_control, cache_page
from django.views.decorators.vary import vary_on_cookie

from codex.urls.const import COVER_MAX_AGE, PAGE_MAX_AGE
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
        cache_page(COVER_MAX_AGE)(
            cache_control(max_age=COVER_MAX_AGE, public=True)(
                vary_on_cookie(CoverView.as_view())
            )
        ),
        name="cover",
    ),
    path(
        "<int:pk>/download/<str:filename>",
        DownloadView.as_view(),
        name="download",
    ),
]
