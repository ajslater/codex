"""Notifier ChannelGroups Consumer."""

from enum import Enum

from channels.generic.websocket import AsyncWebsocketConsumer
from loguru import logger
from typing_extensions import override

ChannelGroups = Enum("ChannelGroups", "ALL ADMIN")


class NotifierConsumer(AsyncWebsocketConsumer):
    """Base Notifier Consumer."""

    def _get_groups(self) -> list[str]:
        """Dynamic groups by user type."""
        groups = [ChannelGroups.ALL.name]
        user = self.scope.get("user") if self.scope else None
        user_channel = None
        if user:
            user_channel = f"user_{user.id}"
        else:
            session = self.scope.get("session")
            if session:
                user_channel = f"user_{session.session_key}"
        if user_channel:
            groups += [user_channel]
        if user and user.is_staff:
            groups += [ChannelGroups.ADMIN.name]
        return groups

    @override
    async def websocket_connect(self, message):
        """Authorize with user and connect websocket to groups."""
        # Set groups for user.
        self.groups = self._get_groups()

        await super().websocket_connect(message)
        logger.trace(f"Websocket connected to {self.groups}")

    @override
    async def disconnect(self, code):
        """Close channels after WebSocket disconnect."""
        await self.close(code)

    async def send_text(self, event):
        """Send message to client."""
        text = event.get("text")
        if not text:
            logger.warning(f"No text in websockets message: {event}")
            return
        await self.send(text)
