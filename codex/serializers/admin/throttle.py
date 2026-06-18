"""ThrottleSettings admin serializer."""

from codex.models import ThrottleSettings
from codex.serializers.models.base import BaseModelSerializer


class ThrottleSettingsSerializer(BaseModelSerializer):
    """
    Serializer for the ThrottleSettings singleton.

    Each int is requests per minute, except ``reset_password`` which is
    per hour. ``0`` disables the limiter for that scope.
    """

    class Meta(BaseModelSerializer.Meta):
        """Specify model and fields."""

        model = ThrottleSettings
        fields = (
            "anon",
            "user",
            "opds",
            "opensearch",
            "reset_password",
        )
