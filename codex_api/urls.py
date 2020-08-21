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

from codex_api.views.auth import LoginView
from codex_api.views.auth import LogoutView
from codex_api.views.auth import RegisterView
from codex_api.views.auth import UserView
from codex_api.views.browser import BrowseView
from codex_api.views.metadata import ComicDownloadView
from codex_api.views.metadata import ComicMetadataView
from codex_api.views.metadata import UserBookmarkFinishedView
from codex_api.views.reader import ComicBookmarkView
from codex_api.views.reader import ComicOpenedView
from codex_api.views.reader import ComicPageView
from codex_api.views.reader import ComicReaderView
from codex_api.views.reader import ComicSettingsView


# from django.urls import include


app_name = "api"
urlpatterns = [
    #
    # Browser
    path("browse/<str:group>/<int:pk>", BrowseView.as_view(), name="browse_objects",),
    path(
        "browse/<str:browse_type>/<int:pk>/mark_read",
        UserBookmarkFinishedView.as_view(),
        name="mark_read",
    ),
    path(
        "comic/<int:pk>/archive.cbz",
        ComicDownloadView.as_view(),
        name="comic_download",
    ),
    #
    # Reader
    path("comic/<int:pk>/open", ComicReaderView.as_view(), name="comic_reader"),
    path("comic/<int:pk>", ComicOpenedView.as_view(), name="comic_info"),
    path(
        "comic/<int:pk>/<int:page_num>/p.jpg",
        ComicPageView.as_view(),
        name="comic_page",
    ),
    path(
        "comic/<int:pk>/<int:page_num>/bookmark",
        ComicBookmarkView.as_view(),
        name="comic_bookmark",
    ),
    path(
        "comic/<int:pk>/settings", ComicSettingsView.as_view(), name="comic_settings",
    ),
    path("comic/settings", ComicSettingsView.as_view(), name="comic_settings",),
    path("comic/<int:pk>/metadata", ComicMetadataView.as_view(), name="comic_metadata"),
    #
    # Auth
    path("auth/register", RegisterView.as_view(), name="register"),
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/me", UserView.as_view(), name="user"),
    path("auth/logout", LogoutView.as_view(), name="user"),
]
