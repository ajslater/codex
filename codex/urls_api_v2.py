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

from codex.views.admin import QueueLibrarianJobs
from codex.views.auth import LoginView, LogoutView, RegisterView, UserView
from codex.views.bookmark import (
    ComicBookmarkView,
    ComicSettingsView,
    UserBookmarkFinishedView,
)
from codex.views.browser import BrowserView
from codex.views.browser_choices import BrowserChoiceView
from codex.views.download import ComicDownloadView
from codex.views.metadata import MetadataView
from codex.views.notify import NotifyView
from codex.views.reader import ComicOpenedView, ComicPageView


CACHE_TIME = 60 * 15
NOTIFY_MAX_AGE = 3

app_name = "api"
urlpatterns = [
    #
    # Browser
    path("<str:group>/<int:pk>/<int:page>", BrowserView.as_view(), name="browser_page"),
    path("<str:group>/<int:pk>/metadata", MetadataView.as_view(), name="metadata"),
    path(
        "<str:group>/<int:pk>/mark_read",
        UserBookmarkFinishedView.as_view(),
        name="mark_read",
    ),
    path(
        "<str:group>/<int:pk>/choices/<str:field_name>",
        BrowserChoiceView.as_view(),
        name="browser_choices",
    ),
    #
    # Reader
    path("c/<int:pk>", ComicOpenedView.as_view(), name="comic_info"),
    path(
        "c/<int:pk>/<int:page>/p.jpg",
        cache_page(CACHE_TIME)(ComicPageView.as_view()),
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
    path("c/<int:pk>/archive.cbz", ComicDownloadView.as_view(), name="comic_download"),
    #
    # Notify
    path(
        "notify",
        cache_control(max_age=NOTIFY_MAX_AGE)(NotifyView.as_view()),
        name="notify",
    ),
    #
    # Auth
    path("auth/register", RegisterView.as_view(), name="register"),
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/me", UserView.as_view(), name="me"),
    path("auth/logout", LogoutView.as_view(), name="logout"),
    path("admin/queue_job", QueueLibrarianJobs.as_view(), name="queue_job"),
]
