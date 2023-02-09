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


# TODO change to AsyncWebsockerConsumer
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

            print(f"Notifier Consumer: Connect to {groups}", self.channel_layer)
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

    async def send_message(self, event):
        """Send message to client."""
        print("NotifierConsumer.send_message:", event)
        text = event["text"]
        await self.send(text)
