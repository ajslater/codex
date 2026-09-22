"""EmailSettings admin serializers."""

from rest_framework.fields import SerializerMethodField
from rest_framework.serializers import (
    BooleanField,
    CharField,
    EmailField,
    IntegerField,
    Serializer,
)

from codex.choices.limits import (
    MAX_FIELD_LEN,
    MAX_NAME_LEN,
    SMTP_PORT,
    SMTP_TIMEOUT_SECONDS,
)
from codex.models import EmailSettings
from codex.serializers.models.base import BaseModelSerializer


class EmailSettingsSerializer(BaseModelSerializer):
    """Serializer for the EmailSettings singleton."""

    # Password is write-only — clients see whether one is set, not the value.
    password = CharField(write_only=True, required=False, allow_blank=True)
    password_set = SerializerMethodField()
    # Declared explicitly rather than left to ModelSerializer. Django
    # derives a PositiveSmallIntegerField's bounds from the SQLite
    # integer range and DRF lifts those into the field, so the save path
    # accepted port 0 and port 70000 while rejecting negatives.
    # Serializer-level, not model ``validators=[...]``: those
    # deconstruct, so they would cost an AlterField migration.
    # ``required=False`` mirrors what ModelSerializer inferred from the
    # model defaults, so declaring them changes the bounds and nothing else.
    port = IntegerField(required=False, min_value=SMTP_PORT[0], max_value=SMTP_PORT[1])
    timeout = IntegerField(
        required=False,
        min_value=SMTP_TIMEOUT_SECONDS[0],
        max_value=SMTP_TIMEOUT_SECONDS[1],
    )
    # The envelope sender of every outbound message, and a CharField on
    # the model with no format check anywhere. Declared here rather than
    # changing the column: the model type would be truthier, but an
    # AlterField migration buys nothing the serializer cannot enforce,
    # and ``put()`` is the only admin write path. ``max_length`` stays
    # explicit so it tracks the column instead of EmailField's 254.
    from_address = EmailField(required=False, allow_blank=True, max_length=MAX_NAME_LEN)

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

    # These carried no ``max_length`` at all while the save path
    # enforces the column width.
    host = CharField(required=False, allow_blank=True, max_length=MAX_NAME_LEN)
    port = IntegerField(required=False, min_value=SMTP_PORT[0], max_value=SMTP_PORT[1])
    user = CharField(required=False, allow_blank=True)
    password = CharField(required=False, allow_blank=True)
    use_tls = BooleanField(required=False)
    use_ssl = BooleanField(required=False)
    timeout = IntegerField(
        required=False,
        min_value=SMTP_TIMEOUT_SECONDS[0],
        max_value=SMTP_TIMEOUT_SECONDS[1],
    )
    from_address = EmailField(required=False, allow_blank=True, max_length=MAX_NAME_LEN)
    subject_prefix = CharField(
        required=False, allow_blank=True, max_length=MAX_FIELD_LEN
    )


class EmailTestSendResponseSerializer(Serializer):
    """Test-send outcome."""

    ok = BooleanField()
    error = CharField(allow_null=True, required=False, default=None)
