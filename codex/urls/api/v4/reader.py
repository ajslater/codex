"""codex:api:v4:reader URL Configuration."""

from django.urls import path

from codex.views.reader.reader import ReaderView
from codex.views.reader.settings import ReaderSettingsView

app_name = "reader"
urlpatterns = [
    path("comics/<int:pk>", ReaderView.as_view(), name="comic"),
    path("settings", ReaderSettingsView.as_view(), name="settings"),
]
