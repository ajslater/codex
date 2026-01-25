"""Browser Choices."""

from types import MappingProxyType

from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP

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
VUETIFY_NULL_CODE = -1
_IDENTIFIER_SOURCES = MappingProxyType(
    {key.value: value for key, value in ID_SOURCE_NAME_MAP.items()}
)
BROWSER_CHOICES = MappingProxyType(
    {
        "bookmark_filter": BROWSER_BOOKMARK_FILTER_CHOICES,
        "order_by": BROWSER_ORDER_BY_CHOICES,
        "top_group": BROWSER_TOP_GROUP_CHOICES,
        "vuetify_null_code": VUETIFY_NULL_CODE,
        "settings_group": {**_GROUP_NAMES},
        "identifier_sources": _IDENTIFIER_SOURCES,
    }
)

DEFAULT_BROWSER_ROUTE = MappingProxyType({"group": "r", "pks": (0,), "page": 1})
_DEFAULT_BROWSER_BREADCRUMBS = (DEFAULT_BROWSER_ROUTE,)
_DEFAULT_SHOW = MappingProxyType({"i": False, "p": True, "s": True, "v": False})
BROWSER_DEFAULTS = MappingProxyType(
    {
        "bookmark_filter": "",
        "breadcrumbs": _DEFAULT_BROWSER_BREADCRUMBS,
        "custom_covers": True,
        "dynamic_covers": True,
        "order_by": "sort_name",
        "order_reverse": False,
        "q": "",
        "show": _DEFAULT_SHOW,
        "top_group": "p",
        "twenty_four_hour_time": False,
        "always_show_filename": False,
        "last_route": DEFAULT_BROWSER_ROUTE,
    }
)

DUMMY_NULL_NAME = "_none_"
