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
from django.views.decorators.cache import cache_page
from django.views.generic.base import RedirectView

from codex.views.frontend import IndexView, browserconfig, webmanifest


CACHE_TIME = 60 * 60

urlpatterns = [
    path(
        "favicon.ico",
        cache_page(CACHE_TIME)(
            RedirectView.as_view(url=staticfiles_storage.url("img/favicon.ico"))
        ),
        name="favicon",
    ),
    path(
        "robots.txt",
        cache_page(CACHE_TIME)(
            RedirectView.as_view(url=staticfiles_storage.url("robots.txt"))
        ),
        name="robots",
    ),
    path(
        "browserconfig.xml", cache_page(CACHE_TIME)(browserconfig), name="browserconfig"
    ),
    path("site.webmanifest", cache_page(CACHE_TIME)(webmanifest), name="webmanifest"),
    path("api/v2/", include("codex.urls_api_v2")),
    path("admin/", admin.site.urls, name="admin"),
    path("", IndexView.as_view(), name="app"),
    re_path(".*", IndexView.as_view(), name="app"),
]


if settings.DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
