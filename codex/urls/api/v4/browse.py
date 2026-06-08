"""
codex:api:v4:browse URL Configuration.

Option A path scheme (see ``tasks/api-v4.md``):

* ``/api/v4/browse/{collection}`` — root listing for that collection
* ``/api/v4/browse/{collection}/{parentIds}`` — listing under one or
  more parent IDs (comma-separated)

Each ``[/{parentIds}]`` pattern is registered twice — once without
the optional segment, once with — so Django's URLconf doesn't need a
"the segment may or may not exist" converter.
"""

from django.urls import path

from codex.views.browser.bookmark import BookmarkView
from codex.views.browser.browser import BrowserHeadView, BrowserView
from codex.views.browser.choices import (
    BrowserChoicesAvailableView,
    BrowserChoicesView,
)
from codex.views.browser.download import CollectionDownloadView
from codex.views.browser.force_update import ForceUpdateView
from codex.views.browser.metadata import MetadataView
from codex.views.browser.saved_settings import (
    SavedBrowserSettingsListView,
    SavedBrowserSettingsLoadView,
)
from codex.views.browser.settings import BrowserSettingsView
from codex.views.lazy_import import LazyImportView

app_name = "browse"


def _pair(suffix: str, view, name: str):
    """Register the same view with and without the optional parent-ids segment."""
    base = f"<collection:collection>{suffix}"
    parented = f"<collection:collection>/<int_list:parent_ids>{suffix}"
    return [
        path(base, view.as_view(), name=f"{name}_root"),
        path(parented, view.as_view(), name=name),
    ]


urlpatterns = [
    *_pair("", BrowserView, "list"),
    *_pair("/head", BrowserHeadView, "head"),
    *_pair("/choices", BrowserChoicesAvailableView, "choices"),
    *_pair("/choices/<str:field_name>", BrowserChoicesView, "choices_field"),
    *_pair("/metadata", MetadataView, "metadata"),
    path(
        "<collection:collection>/<int_list:parent_ids>/download/<str:filename>",
        CollectionDownloadView.as_view(),
        name="download",
    ),
    path(
        "<collection:collection>/<int_list:parent_ids>/import",
        LazyImportView.as_view(),
        name="import",
    ),
    path(
        "<collection:collection>/<int_list:parent_ids>/refresh",
        ForceUpdateView.as_view(),
        name="refresh",
    ),
    path(
        "<collection:collection>/<int_list:parent_ids>/bookmark",
        BookmarkView.as_view(),
        name="bookmark",
    ),
    path(
        "<collection:collection>/settings",
        BrowserSettingsView.as_view(),
        name="settings",
    ),
    path(
        "<collection:collection>/saved-settings",
        SavedBrowserSettingsListView.as_view(),
        name="saved_settings_list",
    ),
    path(
        "<collection:collection>/saved-settings/<int:pk>",
        SavedBrowserSettingsLoadView.as_view(),
        name="saved_settings_detail",
    ),
]
