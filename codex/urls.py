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
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView

from codex.views.frontend import IndexView


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
    path("api/v2/", include("codex.urls_api_v2")),
    path("opds/", include("codex.urls_opds")),
    path("admin/", admin.site.urls),
    path("", include("codex.urls_pwa")),
    path("", IndexView.as_view(), name="app"),
    re_path(".*", IndexView.as_view()),
]


if settings.DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
