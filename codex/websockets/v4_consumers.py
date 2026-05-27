"""
v4 WebSocket consumer.

Subscribes to the same channel groups as the legacy v3 consumer
(``ALL`` / ``ADMIN`` / ``user_<uid>``) and translates each
``send_text`` event into a v4 typed JSON message. The broadcaster
side now carries ``mtime``/``scope`` on the channel-layer event
(see :func:`codex.librarian.notifier.notifierd.NotifierThread._send_task`);
this consumer reads them and merges them into the typed payload so
clients can decide whether to re-fetch without a separate mtime
probe.
"""

import json
from typing import override

from loguru import logger

from codex.websockets.consumers import NotifierConsumer
from codex.websockets.v4_messages import v3_to_v4_payload


class V4NotifierConsumer(NotifierConsumer):
    """Same channel-group ACL as the legacy consumer; types JSON on the wire."""

    @override
    async def send_text(self, event) -> None:
        """Translate ``send_text`` events to v4 typed JSON with mtime+scope."""
        text = event.get("text")
        if not text:
            logger.warning(f"No text in v4 websockets message: {event}")
            return
        payload = v3_to_v4_payload(
            text,
            mtime=event.get("mtime"),
            scope=event.get("scope") or None,
        )
        await self.send(json.dumps(payload, separators=(",", ":")))
