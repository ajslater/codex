"""EmailSettings admin serializers."""

from rest_framework.fields import SerializerMethodField
from rest_framework.serializers import (
    BooleanField,
    CharField,
    EmailField,
    IntegerField,
    Serializer,
)

from codex.models import EmailSettings
from codex.serializers.models.base import BaseModelSerializer


class EmailSettingsSerializer(BaseModelSerializer):
    """Serializer for the EmailSettings singleton."""

    # Password is write-only — clients see whether one is set, not the value.
    password = CharField(write_only=True, required=False, allow_blank=True)
    password_set = SerializerMethodField()

    @staticmethod
    def get_password_set(obj) -> bool:
        """Whether an SMTP password has been configured."""
        return bool(obj.password)

    class Meta(BaseModelSerializer.Meta):
        """Specify model and fields."""

        model = EmailSettings
        fields = (
            "host",
            "port",
            "user",
            "password",
            "password_set",
            "use_tls",
            "use_ssl",
            "timeout",
            "from_address",
            "subject_prefix",
        )
        read_only_fields = ("password_set",)


class EmailTestSendRequestSerializer(Serializer):
    """
    Request body for the Email test-send endpoint.

    All SMTP fields are optional: when present they override the saved
    EmailSettings row for this one send, mirroring the tagging-defaults
    "Test" pattern. ``recipient`` is required.
    """

    recipient = EmailField()

    host = CharField(required=False, allow_blank=True)
    port = IntegerField(required=False, min_value=1, max_value=65_535)
    user = CharField(required=False, allow_blank=True)
    password = CharField(required=False, allow_blank=True)
    use_tls = BooleanField(required=False)
    use_ssl = BooleanField(required=False)
    timeout = IntegerField(required=False, min_value=1, max_value=600)
    from_address = CharField(required=False, allow_blank=True)
    subject_prefix = CharField(required=False, allow_blank=True)


class EmailTestSendResponseSerializer(Serializer):
    """Test-send outcome."""

    ok = BooleanField()
    error = CharField(allow_null=True, required=False, default=None)
