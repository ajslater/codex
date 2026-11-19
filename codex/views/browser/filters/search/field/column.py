"""Parse the field side of a field lookup."""

from types import MappingProxyType
from typing import cast

from django.db.models import CharField, Model
from django.db.models.constants import LOOKUP_SEP
from django.db.models.fields.related import ForeignKey, ManyToManyField

from codex.models.comic import Comic

# Series attributes searched on every comic of the series.
_SERIES_ATTR_FIELDS = ("end_year", "start_year", "status", "summary")
# Search columns that don't search the name of the Comic field they're named for.
_FIELD_TO_REL_SPAN_MAP = MappingProxyType(
    {
        "age_rating_metron": "age_rating__metron__name",
        "age_rating_tagged": "age_rating__name",
        "alternate_series": "reprints__series_name",
        "role": "credits__role__name",
        "credits": "credits__person__name",
        "identifiers": "identifiers__key",
        "sources": "identifiers__source__name",
        "story_arcs": "story_arc_numbers__story_arc__name",
        "volume_to": "volume__number_to",
        **{f"series_{name}": f"series__{name}" for name in _SERIES_ATTR_FIELDS},
    }
)


def _span_field_class(span: str) -> type:
    """Return the class of the span's last field, or ManyToManyField if it crosses one."""
    model = Comic
    field_class = type(None)
    for name in span.split(LOOKUP_SEP):
        field = model._meta.get_field(name)
        if field.many_to_many:
            return ManyToManyField
        field_class = type(field)
        # ``related_model`` is typed ``type[Model] | Literal['self'] | None``;
        # only the last field of a span is not a relation.
        model = cast("type[Model]", field.related_model)
    return field_class


_FIELD_TYPE_MAP = MappingProxyType(
    {
        **{
            field.name: field.__class__
            for field in (*Comic._meta.concrete_fields, *Comic._meta.many_to_many)
        },
        **{
            field_name: _span_field_class(span)
            for field_name, span in _FIELD_TO_REL_SPAN_MAP.items()
        },
        "issue": CharField,
    }
)


def _parse_field_rel(field_name, rel_class) -> tuple:
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


def parse_field(field_name: str) -> tuple:
    """Parse the field size of the query in to database relations."""
    rel_class = _FIELD_TYPE_MAP.get(field_name)
    if not rel_class:
        reason = f"Unknown field specified in search query {field_name}"
        raise ValueError(reason)

    many_to_many = rel_class == ManyToManyField

    rel_class, rel = _parse_field_rel(field_name, rel_class)
    return rel_class, rel, many_to_many
