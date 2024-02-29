"""Browser Settings Filter Serializers."""

from abc import ABC, abstractmethod

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    FloatField,
    IntegerField,
    ListField,
    Serializer,
)

from codex.serializers.choices import CHOICES, VUETIFY_NULL_CODE

VUETIFY_NULL_CODE_STR = str(VUETIFY_NULL_CODE)


class BrowserFilterChoicesSerializer(Serializer):
    """All dynamic filters."""

    age_rating = BooleanField(read_only=True)
    community_rating = BooleanField(read_only=True)
    characters = BooleanField(read_only=True)
    country = BooleanField(read_only=True)
    critical_rating = BooleanField(read_only=True)
    contributors = BooleanField(read_only=True)
    decade = BooleanField(read_only=True)
    genres = BooleanField(read_only=True)
    file_type = BooleanField(read_only=True)
    identifier_type = BooleanField(read_only=True)
    monochrome = BooleanField(read_only=True)
    language = BooleanField(read_only=True)
    locations = BooleanField(read_only=True)
    original_format = BooleanField(read_only=True)
    reading_direction = BooleanField(read_only=True)
    series_groups = BooleanField(read_only=True)
    stories = BooleanField(read_only=True)
    story_arcs = BooleanField(read_only=True)
    tagger = BooleanField(read_only=True)
    tags = BooleanField(read_only=True)
    teams = BooleanField(read_only=True)
    year = BooleanField(read_only=True)


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

    @property
    @classmethod
    @abstractmethod
    def CHILD_CLASS(cls):  # noqa: N802
        """Child field class."""
        raise NotImplementedError

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


class BrowserSettingsFilterSerializer(Serializer):
    """Filter values for settings."""

    bookmark = ChoiceField(
        choices=tuple(CHOICES["bookmarkFilter"].keys()), required=False
    )
    # Dynamic filters
    age_rating = CharListField(allow_blank=True, required=False)
    characters = IntListField(required=False)
    community_rating = FloatListField(required=False)
    country = CharListField(allow_blank=True, required=False)
    contributors = IntListField(required=False)
    critical_rating = FloatListField(required=False)
    decade = DecadeListField(required=False)
    file_type = CharListField(allow_blank=True, required=False)
    genres = IntListField(required=False)
    identifier_type = CharListField(allow_blank=True, required=False)
    language = CharListField(allow_blank=True, required=False)
    locations = IntListField()
    monochrome = BooleanListField(required=False)
    original_format = CharListField(required=False, allow_blank=True)
    reading_direction = CharListField(required=False)
    series_groups = IntListField(required=False)
    stories = IntListField(required=False)
    story_arcs = IntListField(required=False)
    tagger = CharListField(required=False)
    tags = IntListField(required=False)
    teams = IntListField(required=False)
    year = IntListField(required=False)
