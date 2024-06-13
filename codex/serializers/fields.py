"""Custom fields."""

from abc import ABC
from datetime import datetime, timezone

import pycountry
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.fields import Field
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    FloatField,
    IntegerField,
    ListField,
)

from codex.logger.logging import get_logger
from codex.serializers.choices import CHOICES, DUMMY_NULL_NAME, VUETIFY_NULL_CODE
from codex.serializers.route import RouteSerializer

VUETIFY_NULL_CODE_STR = str(VUETIFY_NULL_CODE)
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


def validate_decades(decades):
    """Validate decades."""
    if not decades:
        return
    # * We don't need a whole db call just to be perfectly accurate
    # * -1s are decoded back into None before validation
    exists = False
    for decade in decades:
        if decade is None or decade % 10 == 0:
            exists = True
            break
    if not exists:
        raise ValidationError(_(f"Invalid decade in: {decades}"))


def validate_int_null(values):
    """Use a special code for null.

    Because if a vuetify component has a null key it changes it to the
    array index.
    """
    for index, value in enumerate(values):
        if value == VUETIFY_NULL_CODE:
            values[index] = None
    return values


def validate_str_null(values):
    """Use a special code for null.

    Because if a vuetify component has a null key it changes it to the
    array index. This is the version for CharFields.
    """
    for index, value in enumerate(values):
        if value == VUETIFY_NULL_CODE_STR:
            values[index] = None
    return values


class FilterListField(ListField, ABC):
    """Filter List field with custom arguments."""

    CHILD_CLASS = Field
    VALIDATORS = ()

    def __init__(self, *args, **kwargs):
        """Apply the subclass's arguments."""
        super().__init__(
            *args,
            child=self.CHILD_CLASS(allow_null=True, **kwargs),
            required=False,
            validators=self.VALIDATORS,
        )


class FloatListField(FilterListField):
    """Decimal List Field with validation."""

    CHILD_CLASS = FloatField  # type: ignore
    VALIDATORS = (validate_int_null,)


class IntListField(FilterListField):
    """Integer List Field with validation."""

    CHILD_CLASS = IntegerField  # type: ignore
    VALIDATORS = (validate_int_null,)


class DecadeListField(IntListField):
    """Integer List Field with validation for decades."""

    VALIDATORS = (validate_int_null, validate_decades)


class CharListField(FilterListField):
    """Char List Field with validation."""

    CHILD_CLASS = CharField  # type: ignore
    VALIDATORS = (validate_str_null,)


class BooleanListField(FilterListField):
    """Bool List Field with validation."""

    CHILD_CLASS = BooleanField  # type: ignore
    VALIDATORS = (validate_int_null,)


class BreadcrumbsField(ListField):
    """And Array of Routes."""

    child = RouteSerializer()


class TopGroupField(ChoiceField):
    """Valid Top Groups Only."""

    class_choices = tuple(CHOICES["topGroup"].keys())

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
