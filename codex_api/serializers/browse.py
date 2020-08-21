"""Codex Browser Serializers."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import BooleanField
from rest_framework.serializers import CharField
from rest_framework.serializers import ChoiceField
from rest_framework.serializers import DecimalField
from rest_framework.serializers import IntegerField
from rest_framework.serializers import ListField
from rest_framework.serializers import Serializer

from codex_api.choices.static import CHOICES
from codex_api.serializers.vuetify import VueIntChoiceSerializer


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


class BrowserSettingsShowGroupFlagsSerializer(Serializer):
    """Show Group Flags."""

    p = BooleanField()
    i = BooleanField()
    s = BooleanField()
    v = BooleanField()


class BrowserSettingsSerializer(Serializer):
    """
    Browser Settings that the user can change.

    This is the only browse serializer that's submitted.
    It is also sent to the browser as part of BrowserOpenedSerializer.
    """

    MODEL_FILTER_NONE_CODE = -1
    MODEL_FILTER_KEYS = ("decadeFilter", "charactersFilter")

    bookmarkFilter = ChoiceField(  # noqa: N815
        choices=tuple(CHOICES["bookmarkFilterChoices"].keys())
    )
    decadeFilter = ListField(  # noqa: N815
        child=IntegerField(allow_null=True),
        validators=[validate_decades],
        allow_empty=True,
    )
    charactersFilter = ListField(  # noqa: N815
        child=IntegerField(allow_null=True), allow_empty=True,
    )
    rootGroup = ChoiceField(choices=tuple(CHOICES["rootGroupChoices"].keys()))  # noqa: N815
    sortBy = ChoiceField(choices=tuple(CHOICES["sortChoices"].keys()))  # noqa: N815
    sortReverse = BooleanField()  # noqa: N815
    show = BrowserSettingsShowGroupFlagsSerializer()

    @classmethod
    def fix_model_filters(cls, data):
        """Fix UI not being able to submit null values."""
        for key in cls.MODEL_FILTER_KEYS:
            model_filter = data.get(key)
            for index, value in enumerate(model_filter):
                if value == cls.MODEL_FILTER_NONE_CODE:
                    model_filter[index] = None


class BrowseObjectSerializer(Serializer):
    """Generic browse object."""

    pk = IntegerField(read_only=True)
    group = CharField(read_only=True, max_length=1)
    cover_path = CharField(read_only=True)
    display_name = CharField(read_only=True)
    progress = DecimalField(read_only=True, max_digits=5, decimal_places=2)
    finished = BooleanField(read_only=True, allow_null=True)


class BrowseContainerSerializer(BrowseObjectSerializer):
    """Browse container."""

    child_count = IntegerField(read_only=True, allow_null=True)


class BrowseComicSerializer(BrowseObjectSerializer):
    """Browse comic."""

    header_name = CharField(read_only=True)
    max_page = IntegerField(read_only=True)
    bookmark = IntegerField(read_only=True, allow_null=True)


class BrowseRouteSerializer(Serializer):
    """A vue route for the browser."""

    group = CharField(read_only=True)
    pk = IntegerField(read_only=True)


class BrowserFormChoicesSerializer(Serializer):
    """These choices change with browse context."""

    decadeFilterChoices = VueIntChoiceSerializer(  # noqa: N815
        many=True, read_only=True
    )
    charactersFilterChoices = VueIntChoiceSerializer(  # noqa: N815
        many=True, read_only=True
    )
    enableFolderView = BooleanField(read_only=True)  # noqa: N815


class BrowseListSerializer(Serializer):
    """The main browse list."""

    browseTitle = CharField(read_only=True)  # noqa: N815
    upRoute = BrowseRouteSerializer(allow_null=True)  # noqa: N815
    containerList = ListField(  # noqa: N815
        child=BrowseContainerSerializer(read_only=True),
        allow_empty=True,
        read_only=True,
    )
    comicList = ListField(  # noqa: N815
        child=BrowseComicSerializer(read_only=True), allow_empty=True, read_only=True,
    )
    formChoices = BrowserFormChoicesSerializer(read_only=True)  # noqa: N815


class BrowserOpenedSerializer(Serializer):
    """Component open settings."""

    settings = BrowserSettingsSerializer(read_only=True)
    browseList = BrowseListSerializer(read_only=True)  # noqa: N815
    adminURL = CharField(read_only=True)  # noqa: N815
