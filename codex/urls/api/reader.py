"""codex:api:v3:reader URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_control

from codex.urls.const import PAGE_MAX_AGE
from codex.views.download import DownloadView
from codex.views.reader.page import ReaderPageView
from codex.views.reader.reader import ReaderView
from codex.views.reader.settings import ReaderSettingsView

app_name = "issue"
urlpatterns = [
    #
    #
    # Comic
    path("<int:pk>/download/<str:filename>", DownloadView.as_view(), name="download"),
    #
    #
    # Reader
    path("<int:pk>", ReaderView.as_view(), name="reader"),
    path(
        "<int:pk>/<int:page>/page.jpg",
        cache_control(max_age=PAGE_MAX_AGE, public=True)(ReaderPageView.as_view()),
        name="page",
    ),
    path("settings", ReaderSettingsView.as_view(), name="settings"),
]
