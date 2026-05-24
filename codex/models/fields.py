"""Custom Django fields."""

from decimal import ROUND_DOWN, Decimal
from html import unescape
from typing import Any, override

from cryptography.fernet import (  # pyright: ignore[reportMissingImports]
    Fernet,
    InvalidToken,
)
from django.conf import settings
from django.db.models.fields import (
    CharField,
    DecimalField,
    PositiveSmallIntegerField,
    TextField,
)
from nh3 import clean


def _get_fernet():
    """Lazy Fernet instance from the FIELD_ENCRYPTION_KEY setting."""
    return Fernet(settings.FIELD_ENCRYPTION_KEY)


class EncryptedCharField(CharField):
    """CharField that stores Fernet-encrypted values in the database."""

    @override
    def __init__(self, *args, **kwargs):
        """Default max_length to 512 to accommodate ciphertext expansion."""
        kwargs.setdefault("max_length", 512)
        kwargs.setdefault("blank", True)
        kwargs.setdefault("default", "")
        super().__init__(*args, **kwargs)

    @override
    def get_prep_value(self, value):
        """Encrypt before writing to DB."""
        value = super().get_prep_value(value)
        if not value:
            return value
        return _get_fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, _expression, _connection):
        """Decrypt when reading from DB."""
        if not value:
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return value


class CleaningStringFieldMixin:
    """Sanitizing Mixin for CharField & TextField."""

    def get_prep_value(self, value):
        """Truncate, sanitize, unescape, and strip outer whitespace."""
        if value := super().get_prep_value(value):  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            value = value[: self.max_length]  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            value = clean(value)
            value = unescape(value)
            # Strip outer whitespace last so trailing spaces left over
            # from upstream parsers don't poison FK keys
            # (Country.name / Language.name are the motivating case —
            # the serializer-side pycountry cache lookup relies on
            # exact alpha_2 matches; see
            # ``codex/serializers/fields/browser.py``).
            value = value.strip()
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


class CoercingPositiveSmallIntegerField(
    CoercingSmallIntegerFieldMixin, PositiveSmallIntegerField
):
    """Custom PositiveSmallIntegerField."""

    COERCE_MIN: int = 0


class CoercingDecimalField(DecimalField):
    """Custom DecimalField."""

    def __init__(self, *args, **kwargs) -> None:
        """Init coercing values."""
        super().__init__(*args, **kwargs)
        self._quantize_str = Decimal(f"1e-{self.decimal_places}")
        self._decimal_max = Decimal(10 ** (self.max_digits - 2) - 1)

    @override
    def get_prep_value(self, value) -> Any:
        """Coerce Decimal."""
        prepped_value: Decimal | None = super().get_prep_value(value)
        if prepped_value is not None:
            prepped_value = prepped_value.quantize(
                self._quantize_str, rounding=ROUND_DOWN
            )
            prepped_value = prepped_value.min(self._decimal_max)
        return prepped_value
