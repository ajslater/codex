"""Custom Vuetify fields."""

from functools import cache
from typing import override

from rest_framework.fields import DictField, IntegerField
from rest_framework.serializers import MultipleChoiceField


class StringListMultipleChoiceField(MultipleChoiceField):
    """A Multiple Choice Field expressed as as a comma delimited string."""

    @override
    def to_internal_value(self, data) -> str:
        """Convert comma delimited strings to sets."""
        if isinstance(data, str):
            data = frozenset(data.split(","))
        return super().to_internal_value(data)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]


@cache
def _serializer_field_names(serializer_cls: type) -> tuple[str, ...]:
    """Return the field names of ``serializer_cls`` once per class."""
    # ``serializer_cls()`` runs DRF's metaclass field walk; cache by
    # serializer class so AdminStatsRequestSerializer's five
    # ``SerializerChoicesField`` instances share a single instantiation
    # per target serializer.
    return tuple(serializer_cls().get_fields().keys())


class SerializerChoicesField(StringListMultipleChoiceField):
    """A String List Multiple Choice Field limited to a specified serializer's fields."""

    def __init__(self, serializer=None, **kwargs) -> None:
        """Limit choices to fields from serializers."""
        if not serializer:
            reason = "serializer required for this field."
            raise ValueError(reason)
        super().__init__(choices=_serializer_field_names(serializer), **kwargs)


class CountDictField(DictField):
    """Dict for counting things."""

    child = IntegerField(read_only=True)
