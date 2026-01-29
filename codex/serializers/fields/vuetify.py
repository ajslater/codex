"""Custom Vuetify fields."""

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import (
    BooleanField,
    CharField,
    DecimalField,
    IntegerField,
)

from codex.choices.browser import VUETIFY_NULL_CODE
from codex.models.choices import FileTypeChoices, ReadingDirectionChoices
from codex.serializers.fields.base import CodexChoiceField


class VuetifyNullCodeFieldMixin:
    """Convert Vuetify null codes to None."""

    NULL_CODE: int = VUETIFY_NULL_CODE

    def to_internal_value(self, data):
        """Convert numeric null code to None."""
        return None if data == self.NULL_CODE else data


class VuetifyFileTypeChoiceField(VuetifyNullCodeFieldMixin, CodexChoiceField):  # pyright: ignore[reportIncompatibleMethodOverride]
    """File Type Choice Field."""

    class_choices = FileTypeChoices.values


class VuetifyReadingDirectionChoiceField(VuetifyNullCodeFieldMixin, CodexChoiceField):  # pyright: ignore[reportIncompatibleMethodOverride]
    """Reading Direction Choice Field."""

    class_choices = ReadingDirectionChoices.values


class VuetifyDecimalField(VuetifyNullCodeFieldMixin, DecimalField):  # pyright: ignore[reportIncompatibleMethodOverride]
    """Float Field with null code conversion."""


class VuetifyIntegerField(VuetifyNullCodeFieldMixin, IntegerField):  # pyright: ignore[reportIncompatibleMethodOverride]
    """Integer Field with null code conversion."""


class VuetifyCharField(VuetifyNullCodeFieldMixin, CharField):  # pyright: ignore[reportIncompatibleMethodOverride]
    """Char Field with null code conversion."""

    NULL_CODE: str = str(VUETIFY_NULL_CODE)  # pyright: ignore[reportIncompatibleVariableOverride]


class VuetifyBooleanField(VuetifyNullCodeFieldMixin, BooleanField):  # pyright: ignore[reportIncompatibleMethodOverride]
    """Boolean Field with null code conversion."""


def validate_decade(decade):
    """Validate decades."""
    # * We don't need a whole db call just to be perfectly accurate
    # * -1s are decoded back into None before validation
    if decade is not None and decade % 10 != 0:
        raise ValidationError(_("Invalid decade: ") + f"{decade}")
    return True


class VuetifyDecadeField(VuetifyIntegerField):
    """Integer field with null code conversion and decade validation."""

    VALIDATORS = (validate_decade,)

    def __init__(self, *args, **kwargs):
        """Use decade validator."""
        super().__init__(*args, validators=self.VALIDATORS, **kwargs)
