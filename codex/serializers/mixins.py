"""Serializer mixins."""

from rest_framework.serializers import (
    BooleanField,
    DecimalField,
    IntegerField,
    SerializerMetaclass,
)


UNIONFIX_PREFIX = "unionfix_"


class BrowserAggregateSerializerMixin(metaclass=SerializerMetaclass):
    """Mixin for browser & metadata serializers."""

    UNIONFIX_KEYS = ("cover_path", "issue")

    # Aggregate Annotations
    child_count = IntegerField(read_only=True)

    # UserBookmark annotations
    bookmark = IntegerField(read_only=True)
    finished = BooleanField(read_only=True)
    progress = DecimalField(max_digits=5, decimal_places=2, read_only=True)

    def to_representation(self, instance):
        """
        Copy prefixed input annotations back to regular field names.

        This jankyness because folder/comic unions fail unless
        fields are annotated in the exact same order.
        """
        if instance:
            for key in self.UNIONFIX_KEYS:
                unionfix_key = f"{UNIONFIX_PREFIX}{key}"
                if unionfix_key in instance:
                    instance[key] = instance[unionfix_key]

        return super().to_representation(instance)  # type: ignore
