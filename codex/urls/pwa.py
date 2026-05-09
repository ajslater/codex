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
        # No ``cache_page``: the SW's CSP is captured by the browser
        # at install time from this response, and the browser only
        # swaps the SW when its bytes change. A stale server-side
        # cache pins both content and CSP.
        "serviceworker.js",
        ServiceWorkerView.as_view(),
        name="serviceworker",
    ),
]
