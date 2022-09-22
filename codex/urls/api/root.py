"""codex:api URL Configuration."""
from django.urls import include, path


app_name = "api"
urlpatterns = [
    path("v3/", include("codex.urls.api.v3")),
]
