"""codex:api:v4:reader URL Configuration."""

from django.urls import path

from codex.views.v4.reader import (
    V4ReaderComicView,
    V4ReaderSettingsGlobalView,
)

app_name = "reader"
urlpatterns = [
    path("comics/<int:pk>", V4ReaderComicView.as_view(), name="comic"),
    path("settings", V4ReaderSettingsGlobalView.as_view(), name="settings"),
]
