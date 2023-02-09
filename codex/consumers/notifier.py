"""Notifier Channels Consumer."""
from enum import Enum

from channels.exceptions import (
    AcceptConnection,
    DenyConnection,
    InvalidChannelLayerError,
)
from channels.generic.websocket import AsyncWebsocketConsumer

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
