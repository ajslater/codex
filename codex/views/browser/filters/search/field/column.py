"""Parse the field side of a field lookup."""

from types import MappingProxyType

from django.db.models import (
    CharField,
)
from django.db.models.fields.related import ForeignKey, ManyToManyField

from codex.logger.logging import get_logger
from codex.views.browser.filters.search.aliases import FIELD_TYPE_MAP

_FIELD_TO_REL_SPAN_MAP = MappingProxyType(
    {
        "role": "contributors__role__name",
        "contributors": "contributors__person__name",
        "identifier": "identifier__nss",
        "identirier_type": "identifier__identifier_type__name",
        "story_arcs": "story_arc_number__story_arc__name",
    }
)

LOG = get_logger(__name__)


def _parse_field_rel(field_name, rel_class):
    """Set rel to comic attribute or relation span."""
    rel = _FIELD_TO_REL_SPAN_MAP.get(field_name, "")
    if not rel and rel_class in (ForeignKey, ManyToManyField):
        # This must be after the special span maps
        rel = f"{field_name}__name"

    if rel.endswith("name"):
        rel_class = CharField

    if not rel:
        # Comic attribute
        rel = field_name

    return rel_class, rel


def parse_field(field_name: str):
    """Parse the field size of the query in to database relations."""
    rel_class = FIELD_TYPE_MAP.get(field_name)
    if not rel_class:
        reason = f"Unknown field specified in search query {field_name}"
        raise ValueError(reason)

    many_to_many = rel_class == ManyToManyField

    rel_class, rel = _parse_field_rel(field_name, rel_class)
    return rel_class, rel, many_to_many
