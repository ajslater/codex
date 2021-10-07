"""Bookmark related Serializers."""

from rest_framework.serializers import (
    BooleanField,
    ChoiceField,
    ModelSerializer,
    Serializer,
)

from codex.models import UserBookmark
from codex.serializers.webpack import CHOICES


FIT_TO_CHOICES = tuple(CHOICES["fitTo"].keys())


class UserBookmarkFinishedSerializer(ModelSerializer):
    """The finished field of the UserBookmark."""

    class Meta:
        """Model spec."""

        model = UserBookmark
        fields = ("finished",)


class ComicReaderSettingsSerializer(Serializer):
    """Reader settings the user can change."""

    fitTo = ChoiceField(  # noqa: N815
        choices=FIT_TO_CHOICES,
        allow_null=True,
        required=False,
    )
    twoPages = BooleanField(allow_null=True, required=False)  # noqa: N815
