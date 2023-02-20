"""Notifier ChannelGroups Consumer."""
from enum import Enum

from channels.generic.websocket import AsyncWebsocketConsumer

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
