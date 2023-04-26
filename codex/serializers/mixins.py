"""Serializer mixins."""
from rest_framework.serializers import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    IntegerField,
    Serializer,
)


class BrowserAggregateBaseSerializerMixin(Serializer):
    """Mixin for browser, opds & metadata serializers."""

    group = CharField(read_only=True, max_length=1)

    # Aggregate Annotations
    child_count = IntegerField(read_only=True)
    cover_pk = IntegerField(read_only=True)

    # Bookmark annotations
    page = IntegerField(read_only=True)
    bookmark_updated_at = DateTimeField(read_only=True, allow_null=True)


class BrowserAggregateSerializerMixin(BrowserAggregateBaseSerializerMixin):
    """Mixin for browser & metadata serializers."""

    finished = BooleanField(read_only=True)
    progress = DecimalField(
        max_digits=5, decimal_places=2, read_only=True, coerce_to_string=False
    )


class BrowserCardOPDSBaseSerializer(BrowserAggregateSerializerMixin):
    """Common base for Browser Card and OPDS serializer."""

    pk = IntegerField(read_only=True)
    publisher_name = CharField(read_only=True)
    series_name = CharField(read_only=True)
    volume_name = CharField(read_only=True)
    name = CharField(read_only=True)
    issue = DecimalField(
        max_digits=16,
        decimal_places=3,
        read_only=True,
        coerce_to_string=False,
    )
    issue_suffix = CharField(read_only=True)
    order_value = CharField(read_only=True)
    page_count = IntegerField(read_only=True)


class OKSerializer(Serializer):
    """Default serializer for views without much response."""

    ok = BooleanField(default=True)
