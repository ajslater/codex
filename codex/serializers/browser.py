"""Serializers for the browser view."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import BooleanField
from rest_framework.serializers import CharField
from rest_framework.serializers import ChoiceField
from rest_framework.serializers import DecimalField
from rest_framework.serializers import IntegerField
from rest_framework.serializers import ListField
from rest_framework.serializers import Serializer
from rest_framework.serializers import SerializerMethodField

from codex.librarian.queue import QUEUE
from codex.librarian.queue import ComicCoverCreateTask
from codex.serializers.webpack import CHOICES
from codex.serializers.webpack import VUETIFY_NULL_CODE


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


class FilterListField(ListField):
    """Filter List field with custom arguments."""

    def __init__(self, *args, **kwargs):
        """Apply the subclass's arguments."""
        validators = self.VALIDATORS + kwargs.pop("validators", tuple())
        super().__init__(
            *args,
            child=self.CHILD_CLASS(allow_null=True),
            validators=validators,
            **kwargs,
        )


class IntListField(FilterListField):
    """Integer List Field with validation."""

    CHILD_CLASS = IntegerField
    VALIDATORS = (validate_int_null,)


class CharListField(ListField):
    """Char List Field with validation."""

    CHILD_CLASS = CharField
    VALIDATORS = (validate_str_null,)


class BrowserSettingsFilterSerializer(Serializer):
    """Filter values for settings."""

    bookmark = ChoiceField(  # noqa: N815
        choices=tuple(CHOICES["bookmarkFilter"].keys())
    )
    # Dynamic filters
    characters = IntListField()
    country = CharListField()
    creators = IntListField()
    critical_rating = CharListField()
    decade = IntListField(validators=(validate_decades,))
    format = CharListField()
    genres = IntListField()
    language = CharListField()
    locations = IntListField()
    maturity_rating = CharListField()
    read_ltr = ListField(child=BooleanField())
    series_groups = IntListField()
    story_arcs = IntListField()
    tags = IntListField()
    teams = IntListField()
    user_rating = CharListField()
    year = IntListField()


class BrowserSettingsSerializer(Serializer):
    """
    Browser Settings that the user can change.

    This is the only browse serializer that's submitted.
    It is also sent to the browser as part of BrowserOpenedSerializer.
    """

    filters = BrowserSettingsFilterSerializer()
    rootGroup = ChoiceField(choices=tuple(CHOICES["rootGroup"].keys()))  # noqa: N815
    sortBy = ChoiceField(choices=tuple(CHOICES["sort"].keys()))  # noqa: N815
    sortReverse = BooleanField()  # noqa: N815
    show = BrowserSettingsShowGroupFlagsSerializer()


class BrowserCardSerializer(Serializer):
    """Generic browse object."""

    def get_x_cover_path(self, obj):
        """Ensure comic cover exists for any cover_path we send."""
        comic_path = obj.get("x_path")
        cover_path = obj.get("x_cover_path")
        task = ComicCoverCreateTask(comic_path, cover_path, False)
        QUEUE.put(task)
        return cover_path

    pk = IntegerField(read_only=True)
    group = CharField(read_only=True, max_length=1)
    child_count = IntegerField(read_only=True, allow_null=True)
    x_cover_path = SerializerMethodField()
    header_name = CharField(read_only=True)
    series_name = CharField(read_only=True)
    volume_name = CharField(read_only=True)
    x_issue = DecimalField(max_digits=5, decimal_places=1, read_only=True)
    display_name = CharField(read_only=True)
    progress = DecimalField(read_only=True, max_digits=5, decimal_places=2)
    finished = BooleanField(read_only=True, allow_null=True)
    bookmark = IntegerField(read_only=True, allow_null=True)
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

    browserTitle = BrowserTitleSerializer(read_only=True)  # noqa: N815
    upRoute = BrowserRouteSerializer(allow_null=True)  # noqa: N815
    objList = ListField(  # noqa: N815
        child=BrowserCardSerializer(read_only=True),
        allow_empty=True,
        read_only=True,
    )
    numPages = IntegerField(read_only=True)  # noqa: N815
    formChoices = BrowserFormChoicesSerializer(read_only=True)  # noqa: N815
    librariesExist = BooleanField(read_only=True)  # noqa: N815


class VersionsSerializer(Serializer):
    """Codex version information."""

    installed = CharField(read_only=True)
    latest = CharField(read_only=True)


class BrowserOpenedSerializer(Serializer):
    """Component open settings."""

    settings = BrowserSettingsSerializer(read_only=True)
    browserPage = BrowserPageSerializer(read_only=True)  # noqa: N815
    versions = VersionsSerializer(read_only=True)
