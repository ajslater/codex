"""Codex URL Configuration.

https://docs.djangoproject.com/en/dev/topics/http/urls/
"""
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path, register_converter
from django.views.generic.base import RedirectView

from codex.urls.converters import GroupConverter

TIMEOUT = 60 * 60

register_converter(GroupConverter, "group")

urlpatterns = [
    path(
        "favicon.ico",
        RedirectView.as_view(url=staticfiles_storage.url("img/logo-32.webp")),
        name="favicon",
    ),
    path(
        "robots.txt",
        RedirectView.as_view(url=staticfiles_storage.url("robots.txt")),
        name="robots",
    ),
    path("api/", include("codex.urls.api.root")),
    path("opds/", include("codex.urls.opds.root")),
    path("", include("codex.urls.pwa")),
    # The app must be last because it includes a catch-all path
    path("", include("codex.urls.app")),
]
