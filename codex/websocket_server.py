"""Websocket Server."""
import json
import logging

from json import JSONDecodeError

from asgiref.sync import async_to_sync
from django.core.cache import cache

from codex.settings.django_setup import django_setup
from codex.threads import AggregateMessageQueuedThread


django_setup()

LOG = logging.getLogger(__name__)

# Websocket Application
WS_ACCEPT_MSG = {"type": "websocket.accept"}
WS_SEND_MSG = {"type": "websocket.send"}
BROADCAST_CONNS = set()
ADMIN_CONNS = set()


async def websocket_application(scope, receive, send):
    """Websocket application server."""
    LOG.info(f"Starting websocket connection. {scope}")
    NOTIFIER.start()
    while True:
        try:
            event = await receive()

            if event["type"] == "websocket.connect":
                await send(WS_ACCEPT_MSG)

            if event["type"] == "websocket.disconnect":
                break

            if event["type"] == "websocket.receive":
                try:
                    msg = json.loads(event["text"])
                    msg_type = msg.get("type")

                    if (msg_type) == "subscribe":
                        if msg.get("register"):
                            # The librarian doesn't care about broadcasts
                            BROADCAST_CONNS.add(send)
                        else:
                            BROADCAST_CONNS.discard(send)

                        if msg.get("admin"):
                            # Only admins care about admin messages
                            ADMIN_CONNS.add(send)
                        else:
                            ADMIN_CONNS.discard(send)
                    elif msg_type is None:
                        # keep-alive
                        pass
                    else:
                        LOG.warning(f"Bad message type to websockets: {msg_type}")

                except JSONDecodeError as exc:
                    LOG.error(exc)
        except Exception as exc:
            LOG.exception(exc)
    NOTIFIER.join()
    LOG.info("Closing websocket connection.")


class NotifierMessage:
    """Timed message for flood control."""

    BROADCAST = 0
    ADMIN_BROADCAST = 1

    def __init__(self, type, message):
        """Set the message content."""
        self.type = type
        self.message = message


async def _send_msg(conns, text):
    """Construct a ws send message and send to all connections."""
    _send_msg = {"text": text}
    _send_msg.update(WS_SEND_MSG)
    for send in conns:
        await send(_send_msg)


class Notifier(AggregateMessageQueuedThread):
    """Prevent floods of broadcast messages to clients."""

    NAME = "UI-Notifier"

    def _aggregate_items(self, message):
        """Aggregate messages into cache."""
        self.cache[message.message] = message.type

    def _send_all_items(self):
        """Send all messages waiting in the message cache to client."""
        if not self.cache:
            return
        sent_keys = set()
        cache.clear()
        for msg, type in self.cache.items():
            if not self._do_send_item(msg):
                continue
            if type == NotifierMessage.BROADCAST:
                conns = BROADCAST_CONNS
            elif type == NotifierMessage.ADMIN_BROADCAST:
                conns = ADMIN_CONNS
            else:
                conns = None
            if conns:
                async_to_sync(_send_msg)(BROADCAST_CONNS, msg)
                sent_keys.add(msg)
            else:
                LOG.error(f"invalid message type {type} for message {msg}")
        self._cleanup_cache(sent_keys)


NOTIFIER = Notifier()
