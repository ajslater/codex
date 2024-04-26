"""Cross view utility functions."""

from django.db.models.expressions import Case, F, When
from django.db.models.fields import CharField


def annotate_sort_name(qs):
    """Sort groups by name ignoring articles."""
    # This is used by all kinds of ordering, not just sort_name
    # TODO genericize with reader
    sort_name = Case(
        When(stored_sort_name="", then=F("name")),
        default=F("stored_sort_name"),
        output_field=CharField(),
    )
    return qs.annotate(sort_name=sort_name)
