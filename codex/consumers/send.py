"""Version View."""
import io

from channels.generic.http import AsyncHttpConsumer
from rest_framework.parsers import JSONParser

from codex.consumers.notifier import Channels
from codex.serializers.websocket_send import SendSerializer


class SendConsumer(AsyncHttpConsumer):
    """Get Versions."""

    input_serializer_class = SendSerializer
    _HEADERS = [(b"Content-Type", b"text/plain")]

    async def handle(self, body):
        """Handle incoming json."""
        # TODO auth only accept from localhost
        try:
            print("SendConsumer.handle")
            if not self.channel_layer:
                print("No channel layer found.")
                await self.send_response(
                    503, b"No channel_layer found.", headers=self._HEADERS
                )
                return

            stream = io.BytesIO(body)
            data = JSONParser().parse(stream)
            # data = body.decode("utf-8")
            serializer = self.input_serializer_class(data=data)
            serializer.is_valid(raise_exception=True)

            group = Channels(serializer.validated_data["group"]).name
            message = {
                "type": "send_message",
                "text": serializer.validated_data["text"],
            }
            print(f"SendConsumer.handle {group=}, {message=}")
            await self.channel_layer.group_send(group, message)
            return await self.send_response(200, b"OK", headers=self._HEADERS)
        except Exception as exc:
            print(exc)
