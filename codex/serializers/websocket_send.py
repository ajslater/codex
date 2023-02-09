from rest_framework.serializers import ChoiceField, Serializer
from codex.consumers.notifier import Channels
from codex.serializers.choices import WEBSOCKET_MESSAGES


class SendSerializer(Serializer):
    group = ChoiceField(choices=tuple(e.value for e in Channels))
    text = ChoiceField(WEBSOCKET_MESSAGES)
