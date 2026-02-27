"""Custom Vuetify fields."""

import inspect

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError
from rest_framework.fields import Field, ListField
from rest_framework.serializers import (
    BooleanField,
    CharField,
    DecimalField,
    IntegerField,
)
from typing_extensions import override

from codex.choices.browser import VUETIFY_NULL_CODE
from codex.models.choices import FileTypeChoices, ReadingDirectionChoices
from codex.serializers.fields.base import CodexChoiceField


class VuetifyNullCodeFieldMixin:
    """Convert Vuetify null codes to None."""

    NULL_CODE: int = VUETIFY_NULL_CODE

    def to_internal_value(self, data):
        """Convert numeric null code to None."""
        data = super().to_internal_value(data)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        return None if data == self.NULL_CODE else data

    def to_representation(self, data):
        """Convert None to numeric null code."""
        data = self.NULL_CODE if data is None else data
        return super().to_representation(data)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]


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


def validate_decade(decade) -> bool:
    """Validate decades."""
    # * We don't need a whole db call just to be perfectly accurate
    # * -1s are decoded back into None before validation
    if decade is not None and decade % 10 != 0:
        raise ValidationError(_("Invalid decade: ") + f"{decade}")
    return True


class VuetifyDecadeField(VuetifyIntegerField):
    """Integer field with null code conversion and decade validation."""

    VALIDATORS = (validate_decade,)

    def __init__(self, *args, **kwargs) -> None:
        """Use decade validator."""
        super().__init__(*args, validators=self.VALIDATORS, **kwargs)


class VuetifyListField(ListField):
    """List with a default child and required args."""

    CHILD_CLASS: type[Field] = VuetifyIntegerField
    READ_ONLY: bool = False

    def __init__(
        self, *args, child: type[Field] | Field | None = None, required=False, **kwargs
    ):
        """List with a default child and required."""
        child_instance: Field
        if not child:
            child_instance = self.CHILD_CLASS()
        elif inspect.isclass(child):
            child_instance = child()
        else:
            child_instance = child

        kwargs.setdefault("read_only", self.READ_ONLY)

        super().__init__(*args, child=child_instance, required=required, **kwargs)

    @override
    def to_representation(self, value: list) -> list:
        """
        List of object instances -> List of dicts of primitive datatypes.

        Remove superclass's None filter.
        """
        return [self.child.to_representation(item) for item in value]


class VuetifyReadOnlyListField(VuetifyListField):
    """Vuetify Read Only List Field."""

    READ_ONLY = True
