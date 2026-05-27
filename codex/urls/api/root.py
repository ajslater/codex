"""codex:api URL Configuration."""

from django.urls import include, path

from codex.settings import FEATURES

app_name = "api"
urlpatterns = [
    path("v3/", include("codex.urls.api.v3")),
]
if FEATURES.api_v4:
    urlpatterns += [
        path("v4/", include("codex.urls.api.v4")),
    ]
