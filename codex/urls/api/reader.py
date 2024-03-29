"""codex:api:v3:reader URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_control, cache_page

from codex.urls.const import COMMON_TIMEOUT, COVER_MAX_AGE, PAGE_MAX_AGE
from codex.views.cover import CoverView
from codex.views.download import DownloadView
from codex.views.reader.page import ReaderPageView
from codex.views.reader.reader import ReaderView
from codex.views.reader.session import ReaderSessionView

app_name = "issue"
urlpatterns = [
    #
    #
    # Comic
    path(
        "<int:pk>/cover.webp",
        cache_control(max_age=COVER_MAX_AGE, public=True)(CoverView.as_view()),
        name="cover",
    ),
    path("<int:pk>/download/<str:filename>", DownloadView.as_view(), name="download"),
    #
    #
    # Reader
    path("<int:pk>", cache_page(COMMON_TIMEOUT)(ReaderView.as_view()), name="reader"),
    path(
        "<int:pk>/<int:page>/page.jpg",
        cache_control(max_age=PAGE_MAX_AGE, public=True)(ReaderPageView.as_view()),
        name="page",
    ),
    path("settings", ReaderSessionView.as_view(), name="settings"),
]
