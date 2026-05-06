"""Browser Choices."""

from types import MappingProxyType

from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP

from codex.views.browser.const import BROWSER_FILTER_KEYS

BROWSER_BOOKMARK_FILTER_CHOICES = MappingProxyType(
    {
        "": "All",
        "IN_PROGRESS": "In Progress",
        "READ": "Read",
        "UNREAD": "Unread",
    },
)
BROWSER_ORDER_BY_CHOICES = MappingProxyType(
    {
        "created_at": "Added Time",
        "age_rating": "Age Rating",
        "child_count": "Child Count",
        "critical_rating": "Critical Rating",
        "filename": "Filename",
        "size": "File Size",
        "bookmark_updated_at": "Last Read",
        "sort_name": "Name",
        "page_count": "Page Count",
        "date": "Publish Date",
        "search_score": "Search Score",
        "story_arc_number": "Story Arc Number",
        "updated_at": "Updated Time",
    }
)
_GROUP_NAMES = MappingProxyType(
    {
        "p": "Publishers",
        "i": "Imprints",
        "s": "Series",
        "v": "Volumes",
    }
)
BROWSER_TOP_GROUP_CHOICES = MappingProxyType(
    {
        **_GROUP_NAMES,
        "c": "Issues",
        "f": "Folders",
        "a": "Story Arcs",
    },
)
BROWSER_ROUTE_CHOICES = MappingProxyType({**BROWSER_TOP_GROUP_CHOICES, "r": "Root"})
BROWSER_VIEW_MODE_CHOICES = MappingProxyType(
    {
        "cover": "Cover",
        "table": "Table",
    }
)
BROWSER_TABLE_COVER_SIZE_CHOICES = MappingProxyType(
    {
        "xs": "Tiny",
        "sm": "Small",
    }
)
VUETIFY_NULL_CODE = -1
_IDENTIFIER_SOURCES = MappingProxyType(
    {key.value: value for key, value in ID_SOURCE_NAME_MAP.items()}
)
BROWSER_CHOICES = MappingProxyType(
    {
        "BOOKMARK_FILTER": BROWSER_BOOKMARK_FILTER_CHOICES,
        "ORDER_BY": BROWSER_ORDER_BY_CHOICES,
        "TOP_GROUP": BROWSER_TOP_GROUP_CHOICES,
        "VIEW_MODE": BROWSER_VIEW_MODE_CHOICES,
        "TABLE_COVER_SIZE": BROWSER_TABLE_COVER_SIZE_CHOICES,
        "VUETIFY_NULL_CODE": VUETIFY_NULL_CODE,
        "SETTINGS_GROUP": {**_GROUP_NAMES},
        "IDENTIFIER_SOURCES": _IDENTIFIER_SOURCES,
    }
)

DEFAULT_BROWSER_ROUTE = MappingProxyType({"group": "r", "pks": (0,), "page": 1})

# Top-group values that own a dedicated browser route. For these,
# the URL ``group`` matches the ``top_group``. Everything else
# (publishers / imprints / series / volumes / issues) routes through
# the canonical ``r`` (Root) URL — the per-user ``top_group`` setting
# is what selects the displayed view inside that URL.
_FLAG_GROUP_HAS_OWN_ROUTE = frozenset({"f", "a"})


def admin_default_route_for(top_group: str) -> dict:
    """
    Translate a ``BROWSER_DEFAULT_GROUP`` flag value into a route dict.

    Used by :class:`codex.views.frontend.IndexView` to redirect the bare
    ``/`` URL when no per-user ``last_route`` row exists.
    """
    group = top_group if top_group in _FLAG_GROUP_HAS_OWN_ROUTE else "r"
    return {"group": group, "pks": (0,), "page": 1}


_DEFAULT_SHOW = MappingProxyType({"i": False, "p": True, "s": True, "v": False})
_DEFAULT_FILTERS = MappingProxyType(
    {
        "bookmark": "",
        **dict.fromkeys(BROWSER_FILTER_KEYS, ()),
    }
)
# ──────────────────────────────────────────────────────────────────────
# Browser table-view column registry
#
# Drives the table-view presentation:
#   - the column-picker dialog (every key here is a pickable column),
#   - the ``columns=`` query-param validator on the browser endpoint,
#   - the per-row serializer (which fields to project and how),
#   - the ordering pipeline (clicking a sortable column header sets
#     ``order_by`` to ``sort_key``).
#
# ``sort_key`` MUST resolve to an entry in :data:`BROWSER_ORDER_BY_CHOICES`
# for the column to be effectively sortable. ``m2m`` flags columns whose
# values come from a Many-to-Many relation and must be aggregated; these
# are display-only in v1 (sort_key is ``None``). ``editable`` and
# ``edit_widget`` are reserved for a later phase that will allow inline
# tag-cell editing.
BROWSER_TABLE_COLUMNS = MappingProxyType(
    {
        # Identity
        "cover": {
            "label": "Cover",
            "sort_key": None,
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "name": {
            "label": "Name",
            "sort_key": "sort_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "issue_number": {
            "label": "Issue",
            "sort_key": "issue_number",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "issue_suffix": {
            "label": "Issue Suffix",
            "sort_key": "issue_suffix",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Group hierarchy
        "publisher_name": {
            "label": "Publisher",
            "sort_key": "publisher_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "imprint_name": {
            "label": "Imprint",
            "sort_key": "imprint_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "series_name": {
            "label": "Series",
            "sort_key": "series_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "volume_name": {
            "label": "Volume",
            "sort_key": "volume_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Counts
        "child_count": {
            "label": "Count",
            "sort_key": "child_count",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "issue_count": {
            "label": "Issues",
            "sort_key": "issue_count",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Files
        "file_name": {
            "label": "Filename",
            "sort_key": "filename",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "size": {
            "label": "Size",
            "sort_key": "size",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "page_count": {
            "label": "Pages",
            "sort_key": "page_count",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "file_type": {
            "label": "Type",
            "sort_key": "file_type",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Publishing dates
        "year": {
            "label": "Year",
            "sort_key": "year",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "month": {
            "label": "Month",
            "sort_key": "month",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "day": {
            "label": "Day",
            "sort_key": "day",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "date": {
            "label": "Date",
            "sort_key": "date",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Tagging metadata (single-value FKs)
        "country": {
            "label": "Country",
            "sort_key": "country",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "language": {
            "label": "Language",
            "sort_key": "language",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "original_format": {
            "label": "Format",
            "sort_key": "original_format",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "tagger": {
            "label": "Tagger",
            "sort_key": "tagger",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "scan_info": {
            "label": "Scan Info",
            "sort_key": "scan_info",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "age_rating": {
            "label": "Age Rating",
            "sort_key": "age_rating",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "main_character": {
            "label": "Main Character",
            "sort_key": "main_character",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "main_team": {
            "label": "Main Team",
            "sort_key": "main_team",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Reader / misc
        "reading_direction": {
            "label": "Reading Direction",
            "sort_key": "reading_direction",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "monochrome": {
            "label": "Monochrome",
            "sort_key": "monochrome",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "critical_rating": {
            "label": "Critical Rating",
            "sort_key": "critical_rating",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Timestamps
        "created_at": {
            "label": "Added",
            "sort_key": "created_at",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "updated_at": {
            "label": "Updated",
            "sort_key": "updated_at",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "metadata_mtime": {
            "label": "Metadata Updated",
            "sort_key": "metadata_mtime",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "bookmark_updated_at": {
            "label": "Last Read",
            "sort_key": "bookmark_updated_at",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # M2M relations — display-only in v1; aggregated as JSON arrays at
        # query time, sortable=False is enforced by the registry consistency
        # tests.
        "characters": {
            "label": "Characters",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "credits": {
            "label": "Credits",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "genres": {
            "label": "Genres",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "identifiers": {
            "label": "Identifiers",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "locations": {
            "label": "Locations",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "series_groups": {
            "label": "Series Groups",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "stories": {
            "label": "Stories",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "story_arcs": {
            "label": "Story Arcs",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "tags": {
            "label": "Tags",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "teams": {
            "label": "Teams",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "universes": {
            "label": "Universes",
            "sort_key": None,
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
    }
)

BROWSER_TABLE_DEFAULT_COLUMNS = MappingProxyType(
    {
        "p": ("cover", "name", "child_count"),
        "i": ("cover", "name", "publisher_name", "child_count"),
        "s": ("cover", "name", "publisher_name", "year", "issue_count"),
        "v": ("cover", "name", "series_name", "year", "issue_count"),
        "c": (
            "cover",
            "name",
            "issue_number",
            "series_name",
            "volume_name",
            "year",
            "page_count",
            "size",
        ),
        "f": ("cover", "name", "child_count"),
        "a": ("cover", "name", "publisher_name", "child_count"),
    }
)

BROWSER_DEFAULTS = MappingProxyType(
    {
        "custom_covers": True,
        "dynamic_covers": True,
        "filters": _DEFAULT_FILTERS,
        "order_by": "sort_name",
        "order_reverse": False,
        "search": "",
        "show": _DEFAULT_SHOW,
        "top_group": "p",
        "twenty_four_hour_time": False,
        "always_show_filename": False,
        "last_route": DEFAULT_BROWSER_ROUTE,
        "view_mode": "cover",
        "table_columns": {},
        "table_cover_size": "sm",
    }
)

DUMMY_NULL_NAME = "_none_"
