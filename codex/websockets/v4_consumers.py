"""
v4 WebSocket consumer.

Subscribes to the same channel groups as the v3 consumer so it
receives the same broadcaster fan-out, but translates each ``send_text``
event into a v4 typed JSON message before forwarding it to the
client. The v3 consumer keeps running in parallel (gated by the URL
prefix) so partial migrations don't desync.
"""

import json
from typing import override

from loguru import logger

from codex.websockets.consumers import NotifierConsumer
from codex.websockets.v4_messages import v3_to_v4_payload


class V4NotifierConsumer(NotifierConsumer):
    """Same channel-group ACL as v3 but ships typed JSON on the wire."""

    @override
    async def send_text(self, event) -> None:
        """Translate v3 ``send_text`` events to v4 typed JSON."""
        text = event.get("text")
        if not text:
            logger.warning(f"No text in v4 websockets message: {event}")
            return
        payload = v3_to_v4_payload(text)
        await self.send(json.dumps(payload, separators=(",", ":")))
