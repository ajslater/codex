"""Create the search field alias help map."""

from types import MappingProxyType

_REVERSE_TYPE_MAP = MappingProxyType(
    {
        "Boolean": ["monochrome"],
        "Date": ["date"],
        "DateTime": ["create_at", "updated_at"],
        "Decimal": ["critical_rating", "issue_number"],
        "Integer": [
            "day",
            "month",
            "year",
            "page_count",
            "size",
            "decade",
            "volume",
            "volume_to",
        ],
    }
)
_TYPE_MAP = MappingProxyType(
    {
        field: field_type
        for field_type, fields in _REVERSE_TYPE_MAP.items()
        for field in fields
    }
)


def gen_multipart_field_aliases(field):
    """Generate aliases for fields made of snake_case words."""
    bits = field.split("_")
    aliases = set({field})

    # Singular from plural
    if field.endswith("s"):
        singular = field[:-1]
        if not singular.endswith("ie"):
            aliases.add(singular)

    # Alternate delimiters
    for connector in ("", "-"):
        joined = connector.join(bits)
        aliases.add(joined)

    return frozenset(aliases)


def _get_fieldmap_values(*args):
    values = set()
    for val in args:
        values |= gen_multipart_field_aliases(val)
    return tuple(sorted(values))


FIELDMAP = MappingProxyType(
    {
        "age_rating": ("age",),
        "characters": _get_fieldmap_values("category", "categories", "characters"),
        "collection_title": ("collection",),
        "country": (),
        "credits": _get_fieldmap_values(
            "authors",
            "contributors",
            "creators",
            "credits",
            "people",
            "persons",
        ),
        "created_at": ("created",),
        "critical_rating": _get_fieldmap_values("critical_rating"),
        "day": (),
        "date": (),
        "decade": (),
        "file_type": (
            "filetype",
            "type",
        ),
        "genres": ("genre",),
        "identifiers": _get_fieldmap_values("id", "id_key", "identifier"),
        "imprint": (),
        "issue": (),
        "issue_number": ("number",),
        "issue_suffix": (),
        "locations": ("location", "loc"),
        "language": ("lang"),
        "month": (),
        "monochrome": _get_fieldmap_values("black_and_white"),
        "name": ("title",),
        "notes": (),
        "original_format": ("format",),
        "publisher": (),
        "page_count": ("pages",),
        "path": _get_fieldmap_values(
            "filename",
            "folders",
        ),
        "reading_direction": ("direction", "rd"),
        "review": (),
        "scan_info": ("scan",),
        "series": (),
        "series_groups": _get_fieldmap_values("series_groups"),
        "size": (),
        "sources": _get_fieldmap_values("sources", "id_sources"),
        "stories": ("story",),
        "story_arcs": _get_fieldmap_values("story_arcs", "arcs", "arc"),
        "summary": _get_fieldmap_values("desc", "description", "comments"),
        "tags": ("tag",),
        "tagger": (),
        "teams": ("team",),
        "updated_at": ("updated",),
        "universes": ("universe", "designation"),
        "volume": ("volume_from",),
        "volume_to": (),
        "year": (),
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
