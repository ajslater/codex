"""Custom fields."""

from abc import ABC
from datetime import datetime, timezone

import pycountry
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DictField,
    FloatField,
    IntegerField,
    ListField,
    MultipleChoiceField,
)

from codex.choices import (
    BROWSER_BOOKMARK_FILTER_CHOICES,
    BROWSER_TOP_GROUP_CHOICES,
    DUMMY_NULL_NAME,
    VUETIFY_NULL_CODE,
)
from codex.logger.logging import get_logger
from codex.serializers.route import RouteSerializer

LOG = get_logger(__name__)


class TimestampField(IntegerField):
    """IntegerTimestampField."""

    def to_representation(self, value) -> int:
        """Convert to Jascript millisecond int timestamp from datetime, or castable."""
        if isinstance(value, datetime):
            value = value.timestamp()
        return int(float(value) * 1000)

    def to_internal_value(self, data) -> datetime:  # type: ignore
        """Convert from castable, likely string to datetime."""
        return datetime.fromtimestamp(float(data) / 1000, tz=timezone.utc)


def validate_decade(decade):
    """Validate decades."""
    # * We don't need a whole db call just to be perfectly accurate
    # * -1s are decoded back into None before validation
    if decade is not None and decade % 10 != 0:
        raise ValidationError(_(f"Invalid decade: {decade}"))
    return True


class VuetifyNullCodeFieldMixin:
    """Convert Vuetify null codes to None."""

    NULL_CODE = VUETIFY_NULL_CODE

    def to_internal_value(self, data):
        """Convert numeric null code to None."""
        return None if data == self.NULL_CODE else data


class VuetifyFloatField(VuetifyNullCodeFieldMixin, FloatField):  # type: ignore
    """Float Field with null code conversion."""


class VuetifyIntegerField(VuetifyNullCodeFieldMixin, IntegerField):  # type: ignore
    """Integer Field with null code conversion."""


class VuetifyCharField(VuetifyNullCodeFieldMixin, CharField):  # type: ignore
    """Char Field with null code conversion."""

    NULL_CODE = str(VUETIFY_NULL_CODE)


class VuetifyBooleanField(VuetifyNullCodeFieldMixin, BooleanField):  # type: ignore
    """Boolean Field with null code conversion."""


class BookmarkFilterField(ChoiceField):
    """Bookmark Choice Field."""

    def __init__(self, *args, **kwargs):
        """Use bookmark filter choices."""
        super().__init__(
            *args, choices=tuple(BROWSER_BOOKMARK_FILTER_CHOICES.keys()), **kwargs
        )


class VuetifyDecadeField(VuetifyIntegerField):
    """Integer field with null code conversion and decade validation."""

    VALIDATORS = (validate_decade,)

    def __init__(self, *args, **kwargs):
        """Use decade validator."""
        super().__init__(*args, validators=self.VALIDATORS, **kwargs)


class BreadcrumbsField(ListField):
    """And Array of Routes."""

    child = RouteSerializer()


class TopGroupField(ChoiceField):
    """Valid Top Groups Only."""

    class_choices = tuple(BROWSER_TOP_GROUP_CHOICES.keys())

    def __init__(self, *args, **kwargs):
        """Initialize with choices."""
        super().__init__(*args, choices=self.class_choices, **kwargs)


class PyCountryField(CharField, ABC):
    """Serialize to a long pycountry name."""

    LOOKUP_MODULE = pycountry.countries
    _ALPHA_2_LEN = 2

    def to_representation(self, value):
        """Lookup the name with pycountry, just copy the value on fail."""
        if not value:
            return ""
        if value == DUMMY_NULL_NAME:
            return value
        try:
            # fix for https://github.com/flyingcircusio/pycountry/issues/41
            lookup_obj = (
                self.LOOKUP_MODULE.get(alpha_2=value)
                if len(value) == self._ALPHA_2_LEN
                else self.LOOKUP_MODULE.lookup(value)
            )
            # If lookup fails, return the key as the name
        except Exception:
            LOG.warning(f"Could not serialize name with pycountry {value}")
            return value
        else:
            return lookup_obj.name if lookup_obj else value


class CountryField(PyCountryField):
    """Serializer to long country name."""

    LOOKUP_MODULE = pycountry.countries


class LanguageField(PyCountryField):
    """Serializer to long language name."""

    LOOKUP_MODULE = pycountry.languages


class CountDictField(DictField):
    """Dict for counting things."""

    child = IntegerField(read_only=True)


class StringListMultipleChoiceField(MultipleChoiceField):
    """A Multiple Choice Field expressed as as a comma delimited string."""

    def to_internal_value(self, data):
        """Convert comma delimited strings to sets."""
        if isinstance(data, str):
            data = frozenset(data.split(","))
        return super().to_internal_value(data)  # type: ignore


class SerializerChoicesField(StringListMultipleChoiceField):
    """A String List Multiple Choice Field limited to a specified serializer's fields."""

    def __init__(self, *args, serializer=None, **kwargs):
        """Limit choices to fields from serializers."""
        if not serializer:
            reason = "serializer required for this field."
            raise ValueError(reason)
        choices = serializer().get_fields().keys()
        super().__init__(*args, choices=choices, **kwargs)
