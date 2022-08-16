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
from django.urls import path, re_path
from django.views.decorators.cache import cache_control, cache_page

from codex.views.cover import CoverView
from codex.views.download import ComicDownloadView
from codex.views.opds_v1.authentication import AuthenticationView
from codex.views.opds_v1.browser import BrowserFeed, opds_start_view
from codex.views.opds_v1.opensearch import OpenSearchView
from codex.views.reader import ComicPageView


TIMEOUT = 60 * 60
PAGE_MAX_AGE = 60 * 60 * 24 * 7
COVER_MAX_AGE = PAGE_MAX_AGE

app_name = "v1"

urlpatterns = [
    path(
        "opensearch",
        cache_page(TIMEOUT)(OpenSearchView.as_view()),
        name="opensearch",
    ),
    path(
        "<str:group>/<int:pk>/<int:page>",
        BrowserFeed(),
        name="browser",
    ),
    path(
        "c/<int:pk>/<int:page>/p.jpg",
        cache_control(max_age=PAGE_MAX_AGE)(ComicPageView.as_view()),
        name="comic_page",
    ),
    path(
        "c/<int:pk>/cover.webp",
        cache_control(max_age=COVER_MAX_AGE)(CoverView.as_view()),
        name="cover",
    ),
    path("c/<int:pk>/comic.cbz", ComicDownloadView.as_view(), name="download"),
    path(
        "authentication",
        cache_page(TIMEOUT)(AuthenticationView.as_view()),
        name="authentication",
    ),
    re_path(
        ".*",
        opds_start_view,
        name="start",
    ),
]
