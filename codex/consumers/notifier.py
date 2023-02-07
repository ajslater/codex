"""Notifier Channels Consumer."""
from enum import Enum

from channels.exceptions import (
    AcceptConnection,
    DenyConnection,
    InvalidChannelLayerError,
)
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from codex.settings.logging import get_logger


Channels = Enum("Channels", "ALL ADMIN")

LOG = get_logger(__name__)


class NotifierConsumer(AsyncJsonWebsocketConsumer):
    """Base Notifier Consumer."""

    async def websocket_connect(self, _message):
        """Connect websocket to groups."""
        # Authorization
        user = self.scope.get("user")
        if not user:
            return
        try:
            # Dynamic groups by user type
            groups = [Channels.ALL.name]
            if user.is_staff:
                groups += [Channels.ADMIN.name]

            for group in groups:
                await self.channel_layer.group_add(group, self.channel_name)
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

    async def websocket_receive(self, message):
        """Receive websocket message with auth."""
        user = self.scope.get("user")
        if not user:
            return
        await super().websocket_receive(message)

    async def send_message(self, event):
        """Send message to client."""
        message = event["message"]
        await self.send_json({"text": message})
