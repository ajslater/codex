"""Field aliases and types maps."""

from types import MappingProxyType

from django.db.models.fields import CharField
from django.db.models.fields.related import ManyToManyField

from codex.models.comic import Comic


def gen_multipart_field_aliases(field):
    """Generate aliases for fields made of snake_case words."""
    bits = field.split("_")
    aliases = []

    # Singular from plural
    if field.endswith("s"):
        aliases += [field[:-1]]

    # Alternate delimiters
    for connector in ("", "-"):
        joined = connector.join(bits)
        aliases += [joined, joined[:-1]]

    return tuple(sorted(frozenset(aliases)))


FIELDMAP = MappingProxyType(
    {
        "characters": ("category", "character"),
        "community_rating": gen_multipart_field_aliases("community_rating"),
        "contributors": (
            *gen_multipart_field_aliases("authors"),
            "contributor",
            *gen_multipart_field_aliases("creators"),
            *gen_multipart_field_aliases("credits"),
            *gen_multipart_field_aliases("people"),
            *gen_multipart_field_aliases("persons"),
        ),
        "created_at": ("created",),
        "critical_rating": gen_multipart_field_aliases("critical_rating"),
        "genres": ("genre",),
        "file_type": (
            "filetype",
            "type",
        ),
        "identifiers": ("id", "nss", "identifier"),
        "identifier_types": ("idtype", "id_type", "nid", "identifier_type"),
        "issue_number": ("number",),
        "locations": ("location",),
        "monochrome": gen_multipart_field_aliases("black_and_white"),
        "name": ("title",),
        "original_format": ("format",),
        "page_count": ("pages",),
        "reading_direction": ("direction",),
        "path": (
            "filename",
            *gen_multipart_field_aliases("folders"),
        ),
        "series_groups": gen_multipart_field_aliases("series_groups"),
        "scan_info": ("scan",),
        "stories": ("story",),
        "story_arcs": gen_multipart_field_aliases("story_arcs"),
        "summary": ("comments", "description"),
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
