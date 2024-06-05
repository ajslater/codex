"""Serializer mixins."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    IntegerField,
    Serializer,
)

from codex.serializers.browser.filters import IntListField
from codex.serializers.fields import TimestampField


class BrowserAggregateSerializerMixin(Serializer):
    """Mixin for browser, opds & metadata serializers."""

    group = CharField(read_only=True, max_length=1)
    ids = IntListField(read_only=True)

    # Aggregate Annotations
    child_count = IntegerField(read_only=True)
    mtime = TimestampField(read_only=True)

    # Bookmark annotations
    page = IntegerField(read_only=True)
    bookmark_updated_at = DateTimeField(read_only=True, allow_null=True)
    finished = BooleanField(read_only=True)
    progress = DecimalField(
        max_digits=5, decimal_places=2, read_only=True, coerce_to_string=False
    )
