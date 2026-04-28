"""Listens to the Broadcast Queue and sends its messages to channels."""

import asyncio
from queue import Empty
from types import MappingProxyType

from channels.exceptions import InvalidChannelLayerError
from channels.layers import get_channel_layer

from codex.websockets.consumers import ChannelGroups

WS_NORMAL_CLOSURE = 1000


class BroadcastListener:
    """Listens to the Broadcast Queue and sends its messages to channels."""

    _WS_DISCONNECT_EVENT = MappingProxyType(
        {
            "group": ChannelGroups.ALL,
            "message": {
                "type": "websocket_disconnect",
                "code": WS_NORMAL_CLOSURE,
            },
        }
    )

    def __init__(self, logger_, queue) -> None:
        """Initialize."""
        self.log = logger_
        self.queue = queue
        self.channel_layer = get_channel_layer()

    async def broadcast_group(self, event) -> None:
        """Broadcast message to a group of channels.."""
        if not self.channel_layer:
            reason = "No channel layer found"
            raise InvalidChannelLayerError(reason)
        group = event["group"]
        message = event["message"]
        await self.channel_layer.group_send(group, message)

    async def shutdown(self) -> None:
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

    async def listen(self) -> None:
        """Listen to the broadcast queue until a shutdown message."""
        self.log.success(f"{self.__class__.__name__} started.")
        while True:
            try:
                event = await asyncio.to_thread(self.queue.get)
                if event is None:
                    break
                await self.broadcast_group(event)
            except Exception as exc:
                self.log.warning(f"{self.__class__.__name__} listen: {exc}")
        await self.shutdown()
        self.log.info(f"{self.__class__.__name__} shutdown")
