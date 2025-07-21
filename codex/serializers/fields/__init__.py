"""Custom Serializer Fields."""

from codex.serializers.fields.auth import TimestampField, TimezoneField
from codex.serializers.fields.group import BrowseGroupField
from codex.serializers.fields.reader import FitToField, ReadingDirectionField
from codex.serializers.fields.sanitized import SanitizedCharField
from codex.serializers.fields.session import SessionKeyField
from codex.serializers.fields.stats import (
    CountDictField,
    SerializerChoicesField,
    StringListMultipleChoiceField,
)
from codex.serializers.fields.vuetify import (
    VuetifyBooleanField,
    VuetifyCharField,
    VuetifyDecadeField,
    VuetifyDecimalField,
    VuetifyIntegerField,
)

__all__ = (
    "BrowseGroupField",
    "CountDictField",
    "FitToField",
    "ReadingDirectionField",
    "SanitizedCharField",
    "SerializerChoicesField",
    "SessionKeyField",
    "StringListMultipleChoiceField",
    "TimestampField",
    "TimezoneField",
    "VuetifyBooleanField",
    "VuetifyCharField",
    "VuetifyDecadeField",
    "VuetifyDecimalField",
    "VuetifyIntegerField",
)
