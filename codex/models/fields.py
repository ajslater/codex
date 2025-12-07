"""Custom Django fields."""

from decimal import ROUND_DOWN, Decimal
from html import unescape

from django.db.models.fields import (
    CharField,
    DecimalField,
    PositiveSmallIntegerField,
    SmallIntegerField,
    TextField,
)
from nh3 import clean
from typing_extensions import override


class CleaningStringFieldMixin:
    """Sanitizing Mixin for CharField & TextField."""

    def get_prep_value(self, value):
        """Truncate, sanitize and unescape."""
        if value := super().get_prep_value(value):  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            value = value[: self.max_length]  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            value = clean(value)
            value = unescape(value)
        return value


class CleaningCharField(CleaningStringFieldMixin, CharField):
    """Sanitizing Truncating CharField."""


class CleaningTextField(CleaningStringFieldMixin, TextField):
    """Sanitizing Truncating TextField."""


class CoercingSmallIntegerFieldMixin:
    """Custom IntegerField Mixin that coerces values into a range."""

    COERCE_MIN: int = 2**15 * -1
    COERCE_MAX: int = 2**15 - 1

    def get_prep_value(self, value):
        """Coerce int into range before insertion."""
        value = super().get_prep_value(value)  # pyright: ignore[reportAttributeAccessIssue],  # ty: ignore[unresolved-attribute]
        if value is not None:
            value = max(min(value, self.COERCE_MAX), self.COERCE_MIN)
        return value


class CoercingSmallIntegerField(CoercingSmallIntegerFieldMixin, SmallIntegerField):
    """Custom SmallIntegerField."""


class CoercingPositiveSmallIntegerField(
    CoercingSmallIntegerFieldMixin, PositiveSmallIntegerField
):
    """Custom PositiveSmallIntegerField."""

    COERCE_MIN: int = 0


class CoercingDecimalField(DecimalField):
    """Custom DecimalField."""

    def __init__(self, *args, **kwargs):
        """Init coercing values."""
        super().__init__(*args, **kwargs)
        self._quantize_str = Decimal(f"1e-{self.decimal_places}")
        self._decimal_max = Decimal(10 ** (self.max_digits - 2) - 1)

    @override
    def get_prep_value(self, value):
        """Coerce Decimal."""
        prepped_value: Decimal | None = super().get_prep_value(value)
        if prepped_value is not None:
            prepped_value = prepped_value.quantize(
                self._quantize_str, rounding=ROUND_DOWN
            )
            prepped_value = prepped_value.min(self._decimal_max)
        return prepped_value
