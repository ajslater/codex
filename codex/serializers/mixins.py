"""Serializer mixins."""
from rest_framework.serializers import (
    BooleanField,
    DecimalField,
    IntegerField,
    Serializer,
)


UNIONFIX_PREFIX = "unionfix_"


class BrowserAggregateSerializerMixin(Serializer):
    """Mixin for browser & metadata serializers."""

    # Aggregate Annotations
    childCount = IntegerField(  # noqa: N815
        read_only=True, source=UNIONFIX_PREFIX + "child_count"
    )

    # UserBookmark annotations
    bookmark = IntegerField(read_only=True, source=UNIONFIX_PREFIX + "bookmark")
    finished = BooleanField(read_only=True, source=UNIONFIX_PREFIX + "finished")
    progress = DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True,
        coerce_to_string=False,
        source=UNIONFIX_PREFIX + "progress",
    )
