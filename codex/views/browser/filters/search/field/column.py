"""Parse the field side of a field lookup."""

from types import MappingProxyType

from django.db.models import (
    CharField,
)
from django.db.models.fields.related import ForeignKey, ManyToManyField

from codex.logger.logging import get_logger
from codex.views.browser.filters.search.aliases import ALIAS_FIELD_MAP, FIELD_TYPE_MAP

_NAME_REL = "sort_name"
_FIELD_TO_REL_SPAN_MAP = MappingProxyType(
    {
        "role": f"contributors__role__{_NAME_REL}",
        "contributors": f"contributors__person__{_NAME_REL}",
        "identifier": "identifier__nss",
        "identirier_type": f"identifier__identifier_type__{_NAME_REL}",
        "story_arcs": f"story_arc_number__story_arc__{_NAME_REL}",
    }
)

LOG = get_logger(__name__)


def _parse_field_rel(field_name, rel_class):
    """Set rel to comic attribute or relation span."""
    rel = _FIELD_TO_REL_SPAN_MAP.get(field_name, "")
    if not rel and rel_class in (ForeignKey, ManyToManyField):
        # This must be after the special span maps
        rel = f"{field_name}__{_NAME_REL}"

    if rel.endswith(_NAME_REL):
        rel_class = CharField

    if not rel:
        # Comic attribute
        rel = field_name

    return rel_class, rel


def parse_field(field_name: str):
    """Parse the field size of the query in to database relations."""
    field_name = ALIAS_FIELD_MAP.get(field_name, field_name)
    rel_class = FIELD_TYPE_MAP.get(field_name)
    many_to_many = rel_class == ManyToManyField
    if not rel_class:
        return None, None, False

    rel_class, rel = _parse_field_rel(field_name, rel_class)
    return rel_class, rel, many_to_many
