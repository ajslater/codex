from rest_framework.serializers import (
    CharField,
    ChoiceField,
    Serializer,
    ValidationError,
)

from codex.consumers.notifier import Channels
from codex.serializers.choices import WEBSOCKET_MESSAGES
from codex.settings.settings import SECRET_KEY


def is_secret(value):
    if value != SECRET_KEY:
        raise ValidationError("Wrong secret")


class SendSerializer(Serializer):
    group = ChoiceField(choices=tuple(e.value for e in Channels))
    text = ChoiceField(WEBSOCKET_MESSAGES)
    secret_key = CharField(validators=[is_secret])
