"""Serializer mixins."""

from rest_framework.serializers import SerializerMetaclass


UNIONFIX_PREFIX = "unionfix_"


class UnionFixSerializerMixin(metaclass=SerializerMetaclass):
    """Mixin for browser & metadata serializers."""

    UNIONFIX_KEYS = ("cover_path", "issue")

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
