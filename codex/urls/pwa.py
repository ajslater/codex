"""codex:pwa URL Configuration."""
from django.urls import path
from django.views.decorators.cache import cache_page

from codex.views.pwa import (
    ServiceWorkerRegisterView,
    ServiceWorkerView,
    WebManifestView,
)


TIMEOUT = 60 * 60
app_name = "pwa"

urlpatterns = [
    path(
        "manifest.webmanifest",
        cache_page(TIMEOUT)(WebManifestView.as_view()),
        name="manifest",
    ),
    path(
        "serviceworker-register.js",
        cache_page(TIMEOUT)(ServiceWorkerRegisterView.as_view()),
        name="serviceworker_register",
    ),
    path(
        "serviceworker.js",
        cache_page(TIMEOUT)(ServiceWorkerView.as_view()),
        name="serviceworker",
    ),
]
