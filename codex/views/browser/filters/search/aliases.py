"""Field aliases and types maps."""

from types import MappingProxyType

from django.db.models.fields import CharField
from django.db.models.fields.related import ManyToManyField

from codex.models.comic import Comic


def gen_multipart_field_aliases(field):
    """Generate aliases for fields made of snake_case words."""
    bits = field.split("_")
    aliases = set({field})

    # Singular from plural
    if field.endswith("s"):
        aliases.add(field[:-1])

    # Alternate delimiters
    for connector in ("", "-"):
        joined = connector.join(bits)
        aliases.add(joined)

    return frozenset(aliases)


def _get_fieldmap_values(*args, multipart=None):
    values = set(args)
    if multipart:
        for val in multipart:
            values |= gen_multipart_field_aliases(val)
    return tuple(sorted(values))


FIELDMAP = MappingProxyType(
    {
        "characters": _get_fieldmap_values(
            "category", "categories", multipart=["characters"]
        ),
        "credits": _get_fieldmap_values(
            multipart=(
                "authors",
                "contributors",
                "creators",
                "credits",
                "people",
                "persons",
            )
        ),
        "created_at": ("created",),
        "critical_rating": _get_fieldmap_values(multipart=["critical_rating"]),
        "genres": ("genre",),
        "file_type": (
            "filetype",
            "type",
        ),
        "identifiers": ("id", "nss", "identifier"),
        "identifier_types": _get_fieldmap_values(
            "nid", multipart=("id_type", "identifier_types")
        ),
        "issue_number": ("number",),
        "locations": ("location", "loc"),
        "monochrome": _get_fieldmap_values(multipart=["black_and_white"]),
        "name": ("title",),
        "original_format": ("format",),
        "page_count": ("pages",),
        "reading_direction": ("direction", "rd"),
        "path": _get_fieldmap_values(
            "filename",
            multipart=["folders"],
        ),
        "series_groups": _get_fieldmap_values(multipart=["series_groups"]),
        "scan_info": ("scan",),
        "stories": ("story",),
        "story_arcs": _get_fieldmap_values(multipart=["story_arcs"]),
        "summary": _get_fieldmap_values("desc", "description", multipart=["comments"]),
        "tags": ("tag",),
        "teams": ("team",),
        "updated_at": ("updated",),
    }
)


ALIAS_FIELD_MAP = MappingProxyType(
    {value: key for key, values in FIELDMAP.items() for value in values}
)
FIELD_TYPE_MAP = MappingProxyType(
    {
        **{field.name: field.__class__ for field in Comic._meta.get_fields()},
        "role": ManyToManyField,
        "issue": CharField,
    }
)
