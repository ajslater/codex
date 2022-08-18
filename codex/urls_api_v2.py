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
from django.views.decorators.cache import cache_control, cache_page, never_cache
from rest_framework.decorators import api_view
from rest_framework.response import Response

from codex.views.admin import LibrarianStatusViewSet, QueueLibrarianJobs
from codex.views.auth import LoginView, LogoutView, RegisterView, UserView
from codex.views.bookmark import (
    ComicBookmarkView,
    ComicSettingsView,
    UserBookmarkFinishedView,
)
from codex.views.browser import BrowserView
from codex.views.browser_choices import BrowserChoiceView
from codex.views.cover import CoverView
from codex.views.download import ComicDownloadView
from codex.views.metadata import MetadataView
from codex.views.reader import ComicOpenedView, ComicPageView
from codex.views.session import BrowserSessionView, ReaderSessionView
from codex.views.version import VersionView


COVER_MAX_AGE = 60 * 60 * 24 * 7
PAGE_MAX_AGE = 60 * 60 * 24 * 7
VERSIONS_AGE = 60 * 60 * 12
TIMEOUT = 60 * 5


@api_view()
def base_view(_request):
    """Return the api version."""
    # Possibly openapi documentation someday.
    return Response({"API_VERSION": 2})


app_name = "api_v2"
urlpatterns = [
    #
    # Browser & Group
    path(
        "<str:group>/<int:pk>/<int:page>",
        cache_page(TIMEOUT)(BrowserView.as_view()),
        name="browser_page",
    ),
    path(
        "<str:group>/<int:pk>/metadata",
        cache_page(TIMEOUT)(MetadataView.as_view()),
        name="metadata",
    ),
    path(
        "<str:group>/<int:pk>/mark_read",
        UserBookmarkFinishedView.as_view(),
        name="mark_read",
    ),
    path(
        "<str:group>/<int:pk>/choices/<str:field_name>",
        cache_page(TIMEOUT)(BrowserChoiceView.as_view()),
        name="browser_choices",
    ),
    path("session/browser", BrowserSessionView.as_view(), name="session_browser"),
    #
    # Reader & Comic
    path(
        "c/<int:pk>/cover.webp",
        cache_control(max_age=COVER_MAX_AGE)(CoverView.as_view()),
        name="cover",
    ),
    path(
        "c/<int:pk>", cache_page(TIMEOUT)(ComicOpenedView.as_view()), name="comic_info"
    ),
    path(
        "c/<int:pk>/<int:page>/p.jpg",
        cache_control(max_age=PAGE_MAX_AGE)(ComicPageView.as_view()),
        name="comic_page",
    ),
    path(
        "c/<int:pk>/<int:page>/bookmark",
        ComicBookmarkView.as_view(),
        name="comic_bookmark",
    ),
    path(
        "c/<int:pk>/settings",
        never_cache(ComicSettingsView.as_view()),
        name="comic_settings",
    ),
    path("c/<int:pk>/comic.cbz", ComicDownloadView.as_view(), name="archive_download"),
    path("session/reader", ReaderSessionView.as_view(), name="session_reader"),
    #
    # Auth
    path("auth/register", RegisterView.as_view(), name="register"),
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/me", UserView.as_view(), name="me"),
    path("auth/logout", LogoutView.as_view(), name="logout"),
    #
    # Admin
    path("admin/queue_job", QueueLibrarianJobs.as_view(), name="queue_job"),
    path(
        "admin/librarian_status",
        never_cache(LibrarianStatusViewSet.as_view({"get": "list"})),
        name="librarian_status",
    ),
    #
    # Versions
    path(
        "version",
        cache_control(max_age=VERSIONS_AGE)(VersionView.as_view()),
        name="versions",
    ),
    path("", base_view, name="base"),
]
