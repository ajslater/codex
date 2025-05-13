"""Create the search field alias help map."""

from types import MappingProxyType

from codex.views.browser.filters.search.aliases import FIELDMAP

_REVERSE_TYPE_MAP = MappingProxyType(
    {
        "Boolean": ["monochrome"],
        "Date": ["date"],
        "DateTime": ["create_at", "updated_at"],
        "Decimal": ["community_rating", "critical_rating", "issue_number"],
        "Integer": ["day", "month", "year", "page_count", "size", "decade"],
    }
)
_TYPE_MAP = MappingProxyType(
    {
        field: field_type
        for field_type, fields in _REVERSE_TYPE_MAP.items()
        for field in fields
    }
)


def create_search_field_map():
    """Create the search field alias help map."""
    result = {}
    for key, values in FIELDMAP.items():
        result[key] = {
            "type": _TYPE_MAP.get(key, "String"),
            "aliases": tuple(sorted({*values} - {key})),
        }
    return result


SEARCH_FIELDS = create_search_field_map()
