"""Parse the field side of a field lookup."""

from types import MappingProxyType

from django.db.models import CharField
from django.db.models.fields.related import ForeignKey, ManyToManyField

from codex.models.comic import Comic

_FIELD_TO_REL_SPAN_MAP = MappingProxyType(
    {
        "role": "credits__role__name",
        "credits": "credits__person__name",
        "identifiers": "identifiers__key",
        "sources": "identifiers__source__name",
        "story_arcs": "story_arc_number__story_arc__name",
    }
)
_FIELD_TYPE_MAP = MappingProxyType(
    {
        **{field.name: field.__class__ for field in Comic._meta.get_fields()},
        "role": ManyToManyField,
        "issue": CharField,
    }
)


def _parse_field_rel(field_name, rel_class):
    """Set rel to comic attribute or relation span."""
    rel = _FIELD_TO_REL_SPAN_MAP.get(field_name, "")
    if not rel and rel_class in (ForeignKey, ManyToManyField):
        # This must be after the special span maps
        rel = f"{field_name}__name"

    if rel.endswith(("name", "key")):
        rel_class = CharField

    if not rel:
        # Comic attribute
        rel = field_name

    return rel_class, rel


def parse_field(field_name: str):
    """Parse the field size of the query in to database relations."""
    rel_class = _FIELD_TYPE_MAP.get(field_name)
    if not rel_class:
        reason = f"Unknown field specified in search query {field_name}"
        raise ValueError(reason)

    many_to_many = rel_class == ManyToManyField

    rel_class, rel = _parse_field_rel(field_name, rel_class)
    return rel_class, rel, many_to_many
