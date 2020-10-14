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

from codex.views.auth import LoginView
from codex.views.auth import LogoutView
from codex.views.auth import RegisterView
from codex.views.auth import UserView
from codex.views.bookmark import ComicBookmarkView
from codex.views.bookmark import ComicSettingsView
from codex.views.bookmark import UserBookmarkFinishedView
from codex.views.browser import BrowserView
from codex.views.browser_choices import BrowserChoiceView
from codex.views.download import ComicDownloadView
from codex.views.metadata import MetadataView
from codex.views.notify import ScanNotifyView
from codex.views.reader import ComicOpenedView
from codex.views.reader import ComicPageView


app_name = "api"
urlpatterns = [
    #
    # Reader
    path("c/<int:pk>", ComicOpenedView.as_view(), name="comic_info"),
    path(
        "c/<int:pk>/<int:page>/p.jpg",
        ComicPageView.as_view(),
        name="comic_page",
    ),
    path(
        "c/<int:pk>/<int:page>/bookmark",
        ComicBookmarkView.as_view(),
        name="comic_bookmark",
    ),
    path(
        "c/<int:pk>/settings",
        ComicSettingsView.as_view(),
        name="comic_settings",
    ),
    path(
        "c/<int:pk>/archive.cbz",
        ComicDownloadView.as_view(),
        name="comic_download",
    ),
    #
    # Browser
    path(
        "<str:group>/<int:pk>/<int:page>",
        BrowserView.as_view(),
        name="browser_page",
    ),
    path(
        "<str:group>/<int:pk>/metadata",
        MetadataView.as_view(),
        name="metadata",
    ),
    path(
        "<str:group>/<int:pk>/mark_read",
        UserBookmarkFinishedView.as_view(),
        name="mark_read",
    ),
    #
    # Choices
    path(
        "<str:group>/<int:pk>/choices/<str:field_name>",
        BrowserChoiceView.as_view(),
        name="browser_choices",
    ),
    #
    # Notify
    path("notify/scan", ScanNotifyView.as_view(), name="notify_scan"),
    #
    # Auth
    path("auth/register", RegisterView.as_view(), name="register"),
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/me", UserView.as_view(), name="user"),
    path("auth/logout", LogoutView.as_view(), name="user"),
]
