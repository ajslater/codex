"""Version View."""
from channels.generic.websocket import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.serializers import CharField, ChoiceField, Serializer

from codex.consumers.notifier import Channels


class SendSerializer(Serializer):
    group = ChoiceField(choices=tuple(e.value for e in Channels))
    message = CharField()


class SendView(GenericAPIView):
    """Return Codex Versions."""

    input_serializer_class = SendSerializer

    def post(self, request, *args, **kwargs):
        """Get Versions."""
        print("POST", self.request.data)
        serializer = self.input_serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        # TODO auth only accept from localhost
        layer = get_channel_layer()
        if not layer:
            raise ValueError("channels layer not found.")
        group = Channels(serializer.validated_data["group"]).name
        message = {"text": serializer.validated_data["message"]}
        print(f"{group=}, {message=}")
        async_to_sync(layer.group_send)(group, message)

        return Response()
