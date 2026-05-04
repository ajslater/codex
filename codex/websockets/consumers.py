"""Notifier ChannelGroups Consumer."""

from enum import StrEnum
from typing import override

from channels.generic.websocket import AsyncWebsocketConsumer
from loguru import logger


class ChannelGroups(StrEnum):
    """Websocket channel groups every consumer joins."""

    # Explicit string values match the previous ``Enum.name``-based
    # spelling so callers that built channel-name strings from
    # ``ChannelGroups.ALL.name`` keep working when they drop the
    # ``.name`` access.
    ALL = "ALL"
    ADMIN = "ADMIN"


class NotifierConsumer(AsyncWebsocketConsumer):
    """Base Notifier Consumer."""

    def _get_groups(self) -> list[str]:
        """Dynamic groups by user type."""
        groups: list[str] = [ChannelGroups.ALL]
        user = self.scope.get("user") if self.scope else None
        user_channel = None
        if user:
            user_channel = f"user_{user.id}"
        else:
            session = self.scope.get("session")
            if session:
                user_channel = f"user_{session.session_key}"
        if user_channel:
            groups.append(user_channel)
        if user and user.is_staff:
            groups.append(ChannelGroups.ADMIN)
        return groups

    @override
    async def websocket_connect(self, message) -> None:
        """Authorize with user and connect websocket to groups."""
        # Set groups for user.
        self.groups = self._get_groups()

        await super().websocket_connect(message)
        logger.trace(f"Websocket connected to {self.groups}")

    @override
    async def disconnect(self, code) -> None:
        """Close channels after WebSocket disconnect."""
        await self.close(code)

    async def send_text(self, event) -> None:
        """Send message to client."""
        text = event.get("text")
        if not text:
            logger.warning(f"No text in websockets message: {event}")
            return
        await self.send(text)
