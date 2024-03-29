"""Codex URL Configuration.

https://docs.djangoproject.com/en/dev/topics/http/urls/
"""

from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path, register_converter, set_script_prefix
from django.views.generic.base import RedirectView

from codex.settings.settings import ROOT_PATH
from codex.urls.converters import GroupConverter

register_converter(GroupConverter, "group")

if ROOT_PATH:
    # Django 5 bug https://code.djangoproject.com/ticket/35169#comment:11
    set_script_prefix(ROOT_PATH)

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
