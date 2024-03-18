"""Listens to the Broadcast Queue and sends its messages to channels."""

from queue import Empty
from types import MappingProxyType

from channels.exceptions import InvalidChannelLayerError
from channels.layers import get_channel_layer
from wsproto.frame_protocol import CloseReason

from codex.logger_base import LoggerBaseMixin
from codex.websockets.consumers import ChannelGroups


class BroadcastListener(LoggerBaseMixin):
    """Listens to the Broadcast Queue and sends its messages to channels."""

    _WS_DISCONNECT_EVENT = MappingProxyType(
        {
            "group": ChannelGroups.ALL.name,
            "message": {
                "type": "websocket_disconnect",
                "code": CloseReason.NORMAL_CLOSURE.value,
            },
        }
    )

    def __init__(self, queue, log_queue):
        """Initialize."""
        self.init_logger(log_queue)
        self.queue = queue
        self.channel_layer = get_channel_layer()

    async def broadcast_group(self, event):
        """Broadcast message to a group of channels.."""
        if not self.channel_layer:
            reason = "No channel layer found"
            raise InvalidChannelLayerError(reason)
        group = event["group"]
        message = event["message"]
        await self.channel_layer.group_send(group, message)

    async def shutdown(self):
        """Broadcast disconnect message and close the queue."""
        await self.broadcast_group(self._WS_DISCONNECT_EVENT)
        self.log.debug("Sent disconnect to all channels.")
        try:
            while not self.queue.empty():
                self.queue.get_nowait()
        except Empty:
            pass
        self.queue.close()
        self.queue.join_thread()

    async def listen(self):
        """Listen to the broadcast queue until a shutdown message."""
        self.log.info(f"{self.__class__.__name__} started.")
        while True:
            try:
                event = await self.queue.coro_get()
                if event is None:
                    break
                await self.broadcast_group(event)
            except Exception as exc:
                self.log.warning(f"{self.__class__.__name__} listen: {exc}")
        await self.shutdown()
        self.log.info(f"{self.__class__.__name__} shutdown")
