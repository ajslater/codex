"""Version View."""
import io

from channels.exceptions import InvalidChannelLayerError
from channels.generic.http import AsyncHttpConsumer
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.parsers import JSONParser

from codex.consumers.notifier import Channels
from codex.logger.logging import get_logger
from codex.serializers.websocket_send import SendSerializer


LOG = get_logger(__name__)


class SendConsumer(AsyncHttpConsumer):
    """Get Versions."""

    input_serializer_class = SendSerializer
    _HEADERS = [(b"Content-Type", b"text/plain")]

    def _validate_local(self):
        client = self.scope.get("client")
        server = self.scope.get("server")
        if client[0] != server[0]:
            raise NotAuthenticated()

    @classmethod
    def _get_data(cls, body):
        stream = io.BytesIO(body)
        data = JSONParser().parse(stream)
        serializer = cls.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    async def handle(self, body):
        """Handle incoming json."""
        try:
            self._validate_local()
            if not self.channel_layer:
                raise InvalidChannelLayerError(
                    "BACKEND is unconfigured or doesn't support groups"
                )
            data = self._get_data(body)
            group = Channels(data["group"]).name
            message = {
                "type": "send_text",
                "text": data["text"],
            }
            LOG.debug(f"SendConsumer.handle {group=}, {message=}")
            await self.channel_layer.group_send(group, message)
            return await self.send_response(200, b"OK", headers=self._HEADERS)
        except NotAuthenticated as exc:
            LOG.warning(exc)
            await self.send_response(403, b"", headers=self._HEADERS)
        except ValidationError as exc:
            LOG.warning(exc)
            await self.send_response(400, b"Bad Request", headers=self._HEADERS)
        except InvalidChannelLayerError as exc:
            LOG.error(exc)
            await self.send_response(
                503, b"No channel_layer found.", headers=self._HEADERS
            )
        except Exception as exc:
            LOG.exception(exc)
            await self.send_response(500, b"Server Error", headers=self._HEADERS)
