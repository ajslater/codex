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


VUE_MODEL_NULL_CODE = -1


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


def validate_null_filter(values):
    """
    Use a special code for null.

    Because if a vuetify component has a null key it changes it to the
    array index.
    """
    for index, value in enumerate(values):
        if value == VUE_MODEL_NULL_CODE:
            values[index] = None
    return values


class BrowserSettingsShowGroupFlagsSerializer(Serializer):
    """Show Group Flags."""

    p = BooleanField()
    i = BooleanField()
    s = BooleanField()
    v = BooleanField()


class BrowserSettingsFilterSerializer(Serializer):
    """Filter values for settings."""

    bookmark = ChoiceField(  # noqa: N815
        choices=tuple(CHOICES["bookmarkFilter"].keys())
    )
    decade = ListField(  # noqa: N815
        child=IntegerField(allow_null=True),
        validators=(validate_null_filter, validate_decades),
    )
    characters = ListField(  # noqa: N815
        child=IntegerField(allow_null=True),
        validators=(validate_null_filter,),
    )


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
