"""Serializers for the browser view."""
from abc import ABC, abstractmethod

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DecimalField,
    FloatField,
    IntegerField,
    ListField,
    Serializer,
)

from codex.serializers.choices import CHOICES, VUETIFY_NULL_CODE
from codex.serializers.mixins import (
    BrowserAggregateSerializerMixin,
)

VUETIFY_NULL_CODE_STR = str(VUETIFY_NULL_CODE)


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


class BrowserSettingsShowGroupFlagsSerializer(Serializer):
    """Show Group Flags."""

    p = BooleanField()
    i = BooleanField()
    s = BooleanField()
    v = BooleanField()


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
    creators = IntListField(required=False)
    critical_rating = FloatListField(required=False)
    decade = DecadeListField(required=False)
    file_type = CharListField(allow_blank=True, required=False)
    genres = IntListField(required=False)
    language = CharListField(allow_blank=True, required=False)
    locations = IntListField()
    original_format = CharListField(required=False, allow_blank=True)
    read_ltr = ListField(child=BooleanField(allow_null=True), required=False)
    series_groups = IntListField(required=False)
    story_arcs = IntListField(required=False)
    tags = IntListField(required=False)
    teams = IntListField(required=False)
    year = IntListField(required=False)


class BrowserSettingsSerializer(Serializer):
    """Browser Settings that the user can change.

    This is the only browse serializer that's submitted.
    It is also sent to the browser as part of BrowserOpenedSerializer.
    """

    filters = BrowserSettingsFilterSerializer(required=False)
    order_by = ChoiceField(choices=tuple(CHOICES["orderBy"].keys()), required=False)
    order_reverse = BooleanField(required=False)
    q = CharField(allow_blank=True, required=False)
    query = CharField(allow_blank=True, required=False)  # OPDS 2.0
    show = BrowserSettingsShowGroupFlagsSerializer(required=False)
    twenty_four_hour_time = BooleanField(required=False)
    top_group = ChoiceField(choices=tuple(CHOICES["topGroup"].keys()), required=False)
    opds_metadata = BooleanField(required=False)
    limit = IntegerField(required=False)


class BrowserCardSerializer(BrowserAggregateSerializerMixin):
    """Browse card displayed in the browser."""

    pk = IntegerField(read_only=True)
    publisher_name = CharField(read_only=True)
    series_name = CharField(read_only=True)
    volume_name = CharField(read_only=True)
    name = CharField(read_only=True)
    issue = DecimalField(
        max_digits=16,
        decimal_places=3,
        read_only=True,
        coerce_to_string=False,
    )
    issue_suffix = CharField(read_only=True)
    order_value = CharField(read_only=True)
    page_count = IntegerField(read_only=True)
    read_ltr = BooleanField(read_only=True)


class BrowserRouteSerializer(Serializer):
    """A vue route for the browser."""

    group = CharField(read_only=True)
    pk = IntegerField(read_only=True)
    page = IntegerField(read_only=True)


class BrowserAdminFlagsSerializer(Serializer):
    """These choices change with browse context."""

    folder_view = BooleanField(read_only=True)


class BrowserTitleSerializer(Serializer):
    """Elements for constructing the browse title."""

    parent_name = CharField(read_only=True)
    group_name = CharField(read_only=True)
    group_count = IntegerField(read_only=True, allow_null=True)


class BrowserPageSerializer(Serializer):
    """The main browse list."""

    admin_flags = BrowserAdminFlagsSerializer(read_only=True)
    browser_title = BrowserTitleSerializer(read_only=True)
    covers_timestamp = IntegerField(read_only=True)
    issue_max = DecimalField(
        max_digits=16,
        decimal_places=3,
        read_only=True,
        coerce_to_string=False,
    )
    libraries_exist = BooleanField(read_only=True)
    model_group = CharField(read_only=True)
    num_pages = IntegerField(read_only=True)
    groups = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
    books = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
    up_route = BrowserRouteSerializer(allow_null=True, read_only=True)


class BrowserChoicesSerializer(Serializer):
    """Named Model Serailizer with pk = char hack for languages & countries."""

    pk = CharField(read_only=True)
    name = CharField(read_only=True)


class BrowserFilterChoicesSerializer(Serializer):
    """All dynamic filters."""

    age_rating = BooleanField(read_only=True)
    community_rating = BooleanField(read_only=True)
    characters = BooleanField(read_only=True)
    country = BooleanField(read_only=True)
    critical_rating = BooleanField(read_only=True)
    creators = BooleanField(read_only=True)
    decade = BooleanField(read_only=True)
    genres = BooleanField(read_only=True)
    file_type = BooleanField(read_only=True)
    language = BooleanField(read_only=True)
    locations = BooleanField(read_only=True)
    original_format = BooleanField(read_only=True)
    read_ltr = BooleanField(read_only=True)
    series_groups = BooleanField(read_only=True)
    story_arcs = BooleanField(read_only=True)
    tags = BooleanField(read_only=True)
    teams = BooleanField(read_only=True)
    year = BooleanField(read_only=True)
