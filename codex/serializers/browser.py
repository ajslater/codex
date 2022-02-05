"""Serializers for the browser view."""
from abc import ABC

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DecimalField,
    Field,
    IntegerField,
    ListField,
    Serializer,
)

from codex.serializers.choices import CHOICES, VUETIFY_NULL_CODE
from codex.serializers.mixins import BrowserAggregateSerializerMixin


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
    """
    Use a special code for null.

    Because if a vuetify component has a null key it changes it to the
    array index.
    """
    for index, value in enumerate(values):
        if value == VUETIFY_NULL_CODE:
            values[index] = None
    return values


def validate_str_null(values):
    """
    Use a special code for null.

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

    CHILD_CLASS = Field
    VALIDATORS = tuple()

    def __init__(self, *args, **kwargs):
        """Apply the subclass's arguments."""
        super().__init__(
            *args,
            child=self.CHILD_CLASS(allow_null=True, **kwargs),
            validators=self.VALIDATORS,
        )


class DecimalListField(FilterListField):
    """Decimal List Field with validation."""

    CHILD_CLASS = DecimalField
    VALIDATORS = (validate_int_null,)


class IntListField(FilterListField):
    """Integer List Field with validation."""

    CHILD_CLASS = IntegerField
    VALIDATORS = (validate_int_null,)


class DecadeListField(IntListField):
    """Integer List Field with validation for decades."""

    VALIDATORS = (validate_int_null, validate_decades)


class CharListField(FilterListField):
    """Char List Field with validation."""

    CHILD_CLASS = CharField
    VALIDATORS = (validate_str_null,)


class BrowserSettingsFilterSerializer(Serializer):
    """Filter values for settings."""

    bookmark = ChoiceField(  # noqa: N815
        choices=tuple(CHOICES["bookmarkFilter"].keys())
    )
    # Dynamic filters
    community_rating = DecimalListField(max_digits=4, decimal_places=2)
    characters = IntListField()
    country = CharListField()
    creators = IntListField()
    critical_rating = DecimalListField(max_digits=4, decimal_places=2)
    decade = DecadeListField()
    format = CharListField()
    genres = IntListField()
    language = CharListField()
    locations = IntListField()
    age_rating = CharListField()
    read_ltr = ListField(child=BooleanField())
    series_groups = IntListField()
    story_arcs = IntListField()
    tags = IntListField()
    teams = IntListField()
    year = IntListField()


class BrowserSettingsSerializer(Serializer):
    """
    Browser Settings that the user can change.

    This is the only browse serializer that's submitted.
    It is also sent to the browser as part of BrowserOpenedSerializer.
    """

    filters = BrowserSettingsFilterSerializer()
    autoquery = CharField(allow_blank=True)
    topGroup = ChoiceField(choices=tuple(CHOICES["topGroup"].keys()))  # noqa: N815
    orderBy = ChoiceField(choices=tuple(CHOICES["orderBy"].keys()))  # noqa: N815
    orderReverse = BooleanField()  # noqa: N815
    show = BrowserSettingsShowGroupFlagsSerializer()


class BrowserCardSerializer(BrowserAggregateSerializerMixin, Serializer):
    """Browse card displayed in the browser."""

    pk = IntegerField(read_only=True)
    group = CharField(read_only=True, max_length=1)
    cover_path = CharField(read_only=True)
    publisher_name = CharField(read_only=True)
    series_name = CharField(read_only=True)
    volume_name = CharField(read_only=True)
    name = CharField(read_only=True)
    issue = DecimalField(max_digits=5, decimal_places=1, read_only=True)
    order_value = CharField(read_only=True)


class BrowserRouteSerializer(Serializer):
    """A vue route for the browser."""

    group = CharField(read_only=True)
    pk = IntegerField(read_only=True)
    page = IntegerField(read_only=True)


class BrowserFormChoicesSerializer(Serializer):
    """These choices change with browse context."""

    enableFolderView = BooleanField(read_only=True)  # noqa: N815


class BrowserTitleSerializer(Serializer):
    """Elements for constructing the browse title."""

    parentName = CharField(read_only=True, allow_null=True)  # noqa: N815
    groupName = CharField(read_only=True)  # noqa: N815
    groupCount = IntegerField(read_only=True, allow_null=True)  # noqa: N815


class BrowserPageSerializer(Serializer):
    """The main browse list."""

    NUM_AUTOCOMPLETE_QUERIES = 10

    browserTitle = BrowserTitleSerializer(read_only=True)  # noqa: N815
    modelGroup = CharField(read_only=True)  # noqa: N815
    upRoute = BrowserRouteSerializer(allow_null=True)  # noqa: N815
    objList = ListField(  # noqa: N815
        child=BrowserCardSerializer(read_only=True),
        allow_empty=True,
        read_only=True,
    )
    numPages = IntegerField(read_only=True)  # noqa: N815
    formChoices = BrowserFormChoicesSerializer(read_only=True)  # noqa: N815
    librariesExist = BooleanField(read_only=True)  # noqa: N815
    queries = ListField(
        child=CharField(read_only=True), allow_empty=True, read_only=True
    )


class VersionsSerializer(Serializer):
    """Codex version information."""

    installed = CharField(read_only=True)
    latest = CharField(read_only=True)


class BrowserOpenedSerializer(Serializer):
    """Component open settings."""

    settings = BrowserSettingsSerializer(read_only=True)
    browserPage = BrowserPageSerializer(read_only=True)  # noqa: N815
    versions = VersionsSerializer(read_only=True)
