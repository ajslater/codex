"""Bookmark related Serializers."""

from rest_framework.serializers import (
    BooleanField,
    ChoiceField,
    ModelSerializer,
    Serializer,
)

from codex.models import UserBookmark
from codex.serializers.choices import CHOICES


FIT_TO_CHOICES = tuple(CHOICES["fitTo"].keys())


class UserBookmarkFinishedSerializer(ModelSerializer):
    """The finished field of the UserBookmark."""

    class Meta:
        """Model spec."""

        model = UserBookmark
        fields = ("finished",)


# TODO apiv3 move to session serializer and rename to ReaderSettings
class ComicReaderSettingsSerializer(Serializer):
    """Reader settings the user can change."""

    fit_to = ChoiceField(
        choices=FIT_TO_CHOICES,
        allow_null=True,
        required=False,
    )
    two_pages = BooleanField(allow_null=True, required=False)


# TODO apiv3 rework this terrible thing
class ComicReaderBothSettingsSerializer(Serializer):
    """For both the default and local comic settings."""

    globl = ComicReaderSettingsSerializer(read_only=True)
    local = ComicReaderSettingsSerializer(read_only=True)
