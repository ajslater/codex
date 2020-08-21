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
from django.urls import path
from django.views.generic.base import RedirectView

from .views import admin_settings
from .views.browse import BrowseView
from .views.browse_base import ComicCoverView
from .views.browse_base import ComicDownloadView
from .views.folder import FolderView
from .views.reader import ComicPageView
from .views.reader import ComicReadPageView
from .views.reader import ComicReadView


urlpatterns = [
    path("admin/", admin.site.urls, name="admin"),
    path(
        "admin/settings/",
        admin_settings.SettingsListView.as_view(),
        name="admin_settings",
    ),
    path(
        "root_path/create",
        admin_settings.SettingsCreateView.as_view(),
        name="root_path_create",
    ),
    path(
        "root_path/<int:pk>/",
        admin_settings.SettingsUpdateView.as_view(),
        name="root_path_update",
    ),
    path(
        "root_path/<int:pk>/delete",
        admin_settings.SettingsDeleteView.as_view(),
        name="root_path_delete",
    ),
    path(
        "root_path/<pk>/scan/",
        admin_settings.SettingsScanView.as_view(),
        name="root_path_scan",
    ),
    path(
        "root_path/scan_all/",
        admin_settings.SettingsScanAllView.as_view(),
        name="root_path_scan_all",
    ),
    # user views ####
    path("", RedirectView.as_view(url="/browse/"), name="index"),
    path("browse/", RedirectView.as_view(url="/browse/r/0/"), name="browse_root"),
    path("browse/<group>/<int:pk>/", BrowseView.as_view(), name="browse"),
    path("folder/", RedirectView.as_view(url="/folder/0/"), name="folder_root"),
    path("folder/<int:pk>/", FolderView.as_view(), name="folder_top"),
    path("folder/<int:pk>/<path>/", FolderView.as_view(), name="folder"),
    path("comic/<int:pk>/cover.jpg", ComicCoverView.as_view(), name="comic_cover",),
    path(
        "comic/<int:pk>/archive.cbz",
        ComicDownloadView.as_view(),
        name="comic_download",
    ),
    path("comic/<int:pk>/read/", ComicReadView.as_view(), name="comic_read",),
    path(
        "comic/<int:pk>/read/<int:page_num>/",
        ComicReadPageView.as_view(),
        name="comic_read_page",
    ),
    path(
        "comic/<int:pk>/<int:page_num>/p.jpg",
        ComicPageView.as_view(),
        name="comic_page",
    ),
]
