"""
Codex URL Configuration.

https://docs.djangoproject.com/en/dev/topics/http/urls/
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path, re_path, reverse_lazy
from django.views.generic.base import RedirectView


TIMEOUT = 60 * 60

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
    path("admin/", admin.site.urls),
    path("", include("codex.urls.pwa")),
    path("", include("codex.urls.app")),
    re_path(
        ".*",
        RedirectView.as_view(url=reverse_lazy("app:error", kwargs={"code": 404})),
        name="not_found",
    ),
]

if settings.DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
