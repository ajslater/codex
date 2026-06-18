"""codex:api URL Configuration."""

from django.urls import include, path

from codex.settings import FEATURES

app_name = "api"
urlpatterns = []
if FEATURES.api_v4:
    urlpatterns += [
        path("v4/", include("codex.urls.api.v4")),
    ]
