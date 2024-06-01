"""codex:api:v3:auth URL Configuration."""

from django.urls import include, path

from codex.views.auth import TimezoneView
from codex.views.public import AdminFlagsView

app_name = "auth"
urlpatterns = [
    path("", include("rest_registration.api.urls")),
    path("flags/", AdminFlagsView.as_view(), name="flags"),
    path("timezone/", TimezoneView.as_view(), name="timezone"),
]
