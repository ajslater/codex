"""Notifier ChannelGroups Consumer."""
import functools
from enum import Enum

from channels.exceptions import InvalidChannelLayerError, StopConsumer
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from channels.utils import await_many_dispatch

from codex.django_channels.layers import BROADCAST_CHANNEL_NAME
from codex.logger.logging import get_logger

ChannelGroups = Enum("ChannelGroups", "ALL ADMIN")

LOG = get_logger(__name__)


class NotifierConsumer(AsyncWebsocketConsumer):
    """Base Notifier Consumer."""

    @staticmethod
    def _get_groups(user):
        """Dynamic groups by user type."""
        groups = [ChannelGroups.ALL.name]
        if user.is_staff:
            groups += [ChannelGroups.ADMIN.name]
        return groups

    async def __call__(self, scope, receive, send):
        """Dispatches incoming messages to type-based handlers asynchronously.

        Also waits on special AioQueue broadcast channel.
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

        # Special broadcast channel added to the list
        broadcast_receive = functools.partial(
            self.channel_layer.receive, BROADCAST_CHANNEL_NAME
        )
        receivers = [receive, self.channel_receive, broadcast_receive]

        # Store send function
        self.base_send = send
        # Pass messages in from channel layer or client to dispatch method
        try:
            await await_many_dispatch(receivers, self.dispatch)
        except StopConsumer:
            # Exit cleanly
            pass

    async def websocket_connect(self, message):
        """Authorize with user and connect websocket to groups."""
        # Authorization
        user = self.scope.get("user") if self.scope else None
        if not user:
            LOG.warning("Websockets not available for unregistered users.")
            return

        # Set groups for user.
        self.groups = self._get_groups(user)

        await super().websocket_connect(message)
        LOG.debug(f"Websocket connected to {self.groups}")

    async def disconnect(self, code):
        """Close channels after WebSocket disconnect."""
        await self.close(code)

    async def send_text(self, event):
        """Send message to client."""
        text = event.get("text")
        if not text:
            LOG.warning("No text in message")
            return
        await self.send(text)

    async def broadcast_group(self, event):
        """Broadcast message to a group of channels.."""
        if not self.channel_layer:
            raise InvalidChannelLayerError("No channel layer for Broadcast")

        group = event["group"]
        message = event["message"]
        await self.channel_layer.group_send(group, message)
