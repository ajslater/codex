"""Notifier Channels Consumer."""
import functools

from enum import Enum

from asgiref.sync import async_to_sync
from channels.exceptions import (
    AcceptConnection,
    DenyConnection,
    InvalidChannelLayerError,
    StopConsumer,
)
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from channels.utils import await_many_dispatch

from codex.logger.logging import get_logger


Channels = Enum("Channels", "ALL ADMIN")

LOG = get_logger(__name__)


class NotifierConsumer(AsyncWebsocketConsumer):
    """Base Notifier Consumer."""

    @staticmethod
    def _get_groups(user):
        """Dynamic groups by user type."""
        groups = [Channels.ALL.name]
        if user.is_staff:
            groups += [Channels.ADMIN.name]
        LOG.debug(f"Notifier Consumer: Connect to {groups}")
        return groups

    async def __call__(self, scope, receive, send):
        """
        Dispatches incoming messages to type-based handlers asynchronously.
        """
        self.scope = scope

        # Initialize channel layer
        self.channel_layer = get_channel_layer(self.channel_layer_alias)
        if not self.channel_layer:
            raise InvalidChannelLayerError("channel_layer Not Found")
        self.channel_name = await self.channel_layer.new_channel()
        self.channel_receive = functools.partial(
            self.channel_layer.receive, self.channel_name
        )
        broadcast_receive = functools.partial(self.channel_layer.receive, "broadcast")
        receivers = [receive, self.channel_receive, broadcast_receive]

        # Store send function
        self.base_send = send
        # Pass messages in from channel layer or client to dispatch method
        try:
            print(f"{receivers=}")
            await await_many_dispatch(receivers, self.dispatch)
        except StopConsumer:
            # Exit cleanly
            pass

    async def websocket_connect(self, _message):
        """Connect websocket to groups."""
        # Authorization
        user = self.scope.get("user")
        if not user:
            LOG.warning("No websockets without user.")
            return
        groups = self._get_groups(user)
        try:
            for group in groups:
                if self.channel_layer:
                    await self.channel_layer.group_add(group, self.channel_name)
                else:
                    LOG.warning("No channel_layer found")
        except AttributeError as err:
            raise InvalidChannelLayerError(
                "BACKEND is unconfigured or doesn't support groups"
            ) from err
        try:
            await self.connect()
        except AcceptConnection:
            await self.accept()
        except DenyConnection:
            await self.close()

    async def send_text(self, event):
        """Send message to client."""
        text = event.get("text")
        if not text:
            LOG.warning("No text in message")
            return
        await self.send(text)

    async def broadcast(self, event):
        print("NotifierConsumer.BROADCAST", event)
        group = event["group"]
        text = event["text"]

        message = {"type": "send_text", "text": text}

        if not self.channel_layer:
            raise InvalidChannelLayerError("No channel layer for Broadcast")
        await self.channel_layer.group_send(group, message)
