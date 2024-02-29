"""Bookmark Model Serializers."""

from codex.models.bookmark import Bookmark
from codex.serializers.models.base import BaseModelSerializer


class BookmarkSerializer(BaseModelSerializer):
    """Serializer Bookmark."""

    class Meta(BaseModelSerializer.Meta):
        """Configure the model."""

        model = Bookmark
        fields = (
            "finished",
            "fit_to",
            "page",
            "reading_direction",
            "two_pages",
        )


class BookmarkFinishedSerializer(BaseModelSerializer):
    """The finished field of the Bookmark."""

    class Meta(BaseModelSerializer.Meta):
        """Model spec."""

        model = Bookmark
        fields = ("finished",)
