"""codex:api:v3:reader URL Configuration."""
from django.urls import path
from django.views.decorators.cache import cache_control, cache_page

from codex.views.cover import CoverView
from codex.views.download import DownloadView
from codex.views.reader.page import ReaderPageView
from codex.views.reader.reader import ReaderView
from codex.views.reader.session import ReaderSessionView


COVER_MAX_AGE = 60 * 60 * 24 * 7
PAGE_MAX_AGE = 60 * 60 * 24 * 7
TIMEOUT = 60 * 5

app_name = "issue"
urlpatterns = [
    #
    #
    # Comic
    path(
        "<int:pk>/cover.webp",
        cache_control(max_age=COVER_MAX_AGE)(CoverView.as_view()),
        name="cover",
    ),
    path("<int:pk>/download.cbz", DownloadView.as_view(), name="download"),
    #
    #
    # Reader
    path("<int:pk>", cache_page(TIMEOUT)(ReaderView.as_view()), name="reader"),
    path(
        "<int:pk>/<int:page>/page.jpg",
        cache_control(max_age=PAGE_MAX_AGE)(ReaderPageView.as_view()),
        name="page",
    ),
    path("settings", ReaderSessionView.as_view(), name="settings"),
]
