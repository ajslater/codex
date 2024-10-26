"""Custom Vuetify fields."""

from rest_framework.fields import DictField, IntegerField
from rest_framework.serializers import MultipleChoiceField

from codex.logger.logging import get_logger

LOG = get_logger(__name__)


class StringListMultipleChoiceField(MultipleChoiceField):
    """A Multiple Choice Field expressed as as a comma delimited string."""

    def to_internal_value(self, data):
        """Convert comma delimited strings to sets."""
        if isinstance(data, str):
            data = frozenset(data.split(","))
        return super().to_internal_value(data)  # type: ignore[reportIncompatibleMethodOverride]


class SerializerChoicesField(StringListMultipleChoiceField):
    """A String List Multiple Choice Field limited to a specified serializer's fields."""

    def __init__(self, *args, serializer=None, **kwargs):
        """Limit choices to fields from serializers."""
        if not serializer:
            reason = "serializer required for this field."
            raise ValueError(reason)
        choices = serializer().get_fields().keys()
        super().__init__(*args, choices=choices, **kwargs)


class CountDictField(DictField):
    """Dict for counting things."""

    child = IntegerField(read_only=True)
