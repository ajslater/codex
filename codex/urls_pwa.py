"""codex URL Configuration.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path

from codex.views.pwa import (
    OfflineView,
    ServiceWorkerRegisterView,
    ServiceWorkerView,
    WebManifestView,
)


CACHE_TIME = 60 * 15
NOTIFY_MAX_AGE = 3

urlpatterns = [
    path("manifest.webmanifest", WebManifestView.as_view(), name="manifest"),
    path(
        "serviceworkerRegister.js",
        ServiceWorkerRegisterView.as_view(),
        name="serviceworker_register",
    ),
    path("serviceworker.js", ServiceWorkerView.as_view(), name="serviceworker"),
    path("offline", OfflineView.as_view(), name="offline"),
]
