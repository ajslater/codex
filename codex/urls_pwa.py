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
        "serviceworkerRegister.js",
        cache_page(TIMEOUT)(ServiceWorkerRegisterView.as_view()),
        name="serviceworker_register",
    ),
    path(
        "serviceworker.js",
        cache_page(TIMEOUT)(ServiceWorkerView.as_view()),
        name="serviceworker",
    ),
]
