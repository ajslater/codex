"""
Websocket Server.

Places connections into the Notifier, which sends notifications reading
from a queue.
"""
import json

from json import JSONDecodeError
from logging import getLogger

from codex.notifier import Notifier


LOG = getLogger(__name__)


def _handle_websocket_message(event, send):
    """Process websocket messages from client."""
    try:
        text = json.loads(event["text"])
        if not text:
            # keep-alive messages are empty
            return

        type = text.get("type")
        if type == "subscribe":
            Notifier.subscribe(text, send)
        else:
            LOG.warning(f"Bad message type to websockets: {text}")
    except JSONDecodeError as exc:
        LOG.error(exc)


async def websocket_application(_scope, receive, send):
    """Websocket application server."""
    LOG.debug("Starting websocket connection.")
    while True:
        try:
            event = await receive()

            if event["type"] == "websocket.connect":
                await send({"type": "websocket.accept"})

            if event["type"] == "websocket.disconnect":
                break

            if event["type"] == "websocket.receive":
                _handle_websocket_message(event, send)
        except Exception as exc:
            LOG.exception(exc)
            # If a websocket truly breaks, let it die and restart
            break
    LOG.debug("Closing websocket connection.")
