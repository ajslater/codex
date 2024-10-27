"""Custom Vuetify fields."""

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import (
    BooleanField,
    CharField,
    FloatField,
    IntegerField,
)

from codex.choices.browser import VUETIFY_NULL_CODE
from codex.logger.logging import get_logger

LOG = get_logger(__name__)


class VuetifyNullCodeFieldMixin:
    """Convert Vuetify null codes to None."""

    NULL_CODE = VUETIFY_NULL_CODE

    def to_internal_value(self, data):
        """Convert numeric null code to None."""
        return None if data == self.NULL_CODE else data


class VuetifyFloatField(VuetifyNullCodeFieldMixin, FloatField):  # type: ignore[reportIncompatibleMethodOverride]
    """Float Field with null code conversion."""


class VuetifyIntegerField(VuetifyNullCodeFieldMixin, IntegerField):  # type: ignore[reportIncompatibleMethodOverride]
    """Integer Field with null code conversion."""


class VuetifyCharField(VuetifyNullCodeFieldMixin, CharField):  # type: ignore[reportIncompatibleMethodOverride]
    """Char Field with null code conversion."""

    NULL_CODE = str(VUETIFY_NULL_CODE)


class VuetifyBooleanField(VuetifyNullCodeFieldMixin, BooleanField):  # type: ignore[reportIncompatibleMethodOverride]
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
