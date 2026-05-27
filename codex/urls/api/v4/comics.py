"""codex:api:v4:comics URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_control, cache_page
from django.views.decorators.vary import vary_on_cookie

from codex.urls.const import COVER_MAX_AGE, PAGE_MAX_AGE
from codex.views.util import cache_control_2xx
from codex.views.v4.reader import (
    V4ComicBookmarkView,
    V4ComicCoverView,
    V4ComicDownloadView,
    V4ComicPageView,
    V4ComicReaderSettingsView,
)

app_name = "comics"
urlpatterns = [
    path(
        "<int:pk>/bookmark",
        V4ComicBookmarkView.as_view(),
        name="bookmark",
    ),
    path(
        "<int:pk>/reader-settings",
        V4ComicReaderSettingsView.as_view(),
        name="reader_settings",
    ),
    path(
        "<int:pk>/pages/<int:page>",
        cache_control_2xx(max_age=PAGE_MAX_AGE, public=True)(V4ComicPageView.as_view()),
        name="page",
    ),
    path(
        "<int:pk>/cover",
        cache_page(COVER_MAX_AGE)(
            cache_control(max_age=COVER_MAX_AGE, public=True)(
                vary_on_cookie(V4ComicCoverView.as_view())
            )
        ),
        name="cover",
    ),
    path(
        "<int:pk>/download/<str:filename>",
        V4ComicDownloadView.as_view(),
        name="download",
    ),
]
