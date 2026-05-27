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

from codex.views.v4.browse import (
    V4BrowseBookmarkView,
    V4BrowseChoicesFieldView,
    V4BrowseChoicesView,
    V4BrowseDownloadView,
    V4BrowseImportView,
    V4BrowseMetadataView,
    V4BrowseRefreshView,
    V4BrowseSavedSettingsDetailView,
    V4BrowseSavedSettingsListView,
    V4BrowseSettingsView,
    V4BrowseView,
)

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
    *_pair("", V4BrowseView, "list"),
    *_pair("/choices", V4BrowseChoicesView, "choices"),
    *_pair("/choices/<str:field_name>", V4BrowseChoicesFieldView, "choices_field"),
    *_pair("/metadata", V4BrowseMetadataView, "metadata"),
    path(
        "<collection:collection>/<int_list:parent_ids>/download/<str:filename>",
        V4BrowseDownloadView.as_view(),
        name="download",
    ),
    path(
        "<collection:collection>/<int_list:parent_ids>/import",
        V4BrowseImportView.as_view(),
        name="import",
    ),
    path(
        "<collection:collection>/<int_list:parent_ids>/refresh",
        V4BrowseRefreshView.as_view(),
        name="refresh",
    ),
    path(
        "<collection:collection>/<int_list:parent_ids>/bookmark",
        V4BrowseBookmarkView.as_view(),
        name="bookmark",
    ),
    path(
        "<collection:collection>/settings",
        V4BrowseSettingsView.as_view(),
        name="settings",
    ),
    path(
        "<collection:collection>/saved-settings",
        V4BrowseSavedSettingsListView.as_view(),
        name="saved_settings_list",
    ),
    path(
        "<collection:collection>/saved-settings/<int:pk>",
        V4BrowseSavedSettingsDetailView.as_view(),
        name="saved_settings_detail",
    ),
]
