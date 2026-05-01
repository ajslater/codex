"""
Codex URL Configuration.

https://docs.djangoproject.com/en/dev/topics/http/urls/
"""

from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path, register_converter
from django.views.generic.base import RedirectView

from codex.settings import FEATURES
from codex.urls.converters import GroupConverter, IntListConverter
from codex.views.healthcheck import health_check_view

register_converter(GroupConverter, "group")
register_converter(IntListConverter, "int_list")


urlpatterns = []
if FEATURES.schema_graph:
    from schema_graph.views import Schema

    urlpatterns += [
        path("schema/", Schema.as_view()),
    ]
if FEATURES.silk:
    urlpatterns += [
        path("silk/", include("silk.urls", namespace="silk")),
    ]

urlpatterns += [
    path(
        "favicon.ico",
        RedirectView.as_view(url=staticfiles_storage.url("img/logo.svg")),
        name="favicon",
    ),
    path(
        "robots.txt",
        RedirectView.as_view(url=staticfiles_storage.url("robots.txt")),
        name="robots",
    ),
    path("api/", include("codex.urls.api.root")),
    path("opds/", include("codex.urls.opds.root")),
    path("opds", RedirectView.as_view(pattern_name="opds:v1:start")),
    path("health", health_check_view, name="healthcheck"),
    path("", include("codex.urls.pwa")),
    # The app must be last because it includes a catch-all path
    path("", include("codex.urls.app")),
]
