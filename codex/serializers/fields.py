"""Custom fields."""

from abc import ABC
from datetime import datetime
from math import floor

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.fields import Field
from rest_framework.serializers import (
    BooleanField,
    CharField,
    FloatField,
    IntegerField,
    ListField,
)

from codex.serializers.choices import VUETIFY_NULL_CODE

VUETIFY_NULL_CODE_STR = str(VUETIFY_NULL_CODE)


class TimestampField(IntegerField):
    """IntegerTimestampField."""

    def to_representation(self, value):
        """Convert to int from datetime, or castable."""
        if isinstance(value, datetime):
            value = floor(value.timestamp())
        return int(value)

    def to_internal_value(self, data):
        """Convert from castable, likely string."""
        return int(data)


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
