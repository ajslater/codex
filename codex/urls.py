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
from django.contrib import admin
from django.urls import include
from django.urls import path

from codex.auth import RegistrationView
from codex.views.browse import BrowseView
from codex.views.browse_base import ComicDownloadView
from codex.views.browse_base import redirect_browse_root
from codex.views.folder import FolderView
from codex.views.mark_read import MarkRead
from codex.views.reader import ComicPageView
from codex.views.reader import ComicReadPageView
from codex.views.reader import ComicReadView
from codex.views.user_settings import UserSettingsView


urlpatterns = [
    path("", redirect_browse_root, name="index"),
    path("browse/", redirect_browse_root, name="browse_root"),
    path("browse/f/<int:pk>/", FolderView.as_view(), name="folder"),
    path("browse/<group>/<int:pk>/", BrowseView.as_view(), name="browse"),
    path(
        "comic/<int:pk>/archive.cbz",
        ComicDownloadView.as_view(),
        name="comic_download",
    ),
    path("comic/<int:pk>/", ComicReadView.as_view(), name="comic_read",),
    path(
        "comic/<int:pk>/<int:page_num>/",
        ComicReadPageView.as_view(),
        name="comic_read_page",
    ),
    path(
        "comic/<int:pk>/<int:page_num>/p.jpg",
        ComicPageView.as_view(),
        name="comic_page",
    ),
    path("mark_read/<browse_type>/<pk>/", MarkRead.as_view(), name="mark_read",),
    path("settings/", UserSettingsView.as_view(), name="user_settings"),
    # Includes
    path(
        "accounts/register/",
        RegistrationView.as_view(),
        name="django_registration_register",
    ),
    path("accounts/", include("django_registration.backends.one_step.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls, name="admin"),
]
