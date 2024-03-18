"""codex:pwa URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_page

from codex.urls.const import COMMON_TIMEOUT
from codex.views.pwa import (
    ServiceWorkerRegisterView,
    ServiceWorkerView,
    WebManifestView,
)

app_name = "pwa"

urlpatterns = [
    path(
        "manifest.webmanifest",
        cache_page(COMMON_TIMEOUT)(WebManifestView.as_view()),
        name="manifest",
    ),
    path(
        "serviceworker-register.js",
        cache_page(COMMON_TIMEOUT)(ServiceWorkerRegisterView.as_view()),
        name="serviceworker_register",
    ),
    path(
        "serviceworker.js",
        cache_page(COMMON_TIMEOUT)(ServiceWorkerView.as_view()),
        name="serviceworker",
    ),
]
