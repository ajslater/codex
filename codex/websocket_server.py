"""
Websocket Server.

Places connections into the Notifier, which sends notifications reading
from a queue.
"""
import asyncio
import json

from json import JSONDecodeError

from codex.notifier.mp_queue import NOTIFIER_QUEUE
from codex.notifier.tasks import NotifierSubscribeTask
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


def _handle_websocket_message(event, send):
    """Process websocket messages from client."""
    try:
        text = json.loads(event["text"])
        if not text:
            # keep-alive messages are empty
            return

        type = text.get("type")
        if type == "subscribe":
            task = NotifierSubscribeTask(text, True, send)
            NOTIFIER_QUEUE.put(task)
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
                await asyncio.sleep(0)

            if event["type"] == "websocket.disconnect":
                task = NotifierSubscribeTask("", False, send)
                NOTIFIER_QUEUE.put(task)
                break

            if event["type"] == "websocket.receive":
                _handle_websocket_message(event, send)
        except Exception as exc:
            LOG.exception(exc)
            # If a websocket truly breaks, let it die and restart
            break
    LOG.debug("Closing websocket connection.")
