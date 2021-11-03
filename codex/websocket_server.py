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
BROADCAST_CONNS = set()
ADMIN_CONNS = set()


async def websocket_application(scope, receive, send):
    """Websocket application server."""
    LOG.info(f"Starting websocket connection. {scope}")
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
    LOG.info("Closing websocket connection.")


class NotifierMessage:
    """Timed message for flood control."""

    BROADCAST = 0
    ADMIN_BROADCAST = 1

    def __init__(self, type, message):
        """Set the message content."""
        self.type = type
        self.message = message


class Notifier(AggregateMessageQueuedThread):
    """Prevent floods of broadcast messages to clients."""

    NAME = "UI-Notifier"
    WS_SEND_MSG = {"type": "websocket.send"}

    @classmethod
    async def _send_msg(cls, conns, text):
        """Construct a ws send message and send to all connections."""
        send_msg = {"text": text}
        send_msg.update(cls.WS_SEND_MSG)
        for send in conns:
            await send(send_msg)

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
            if conns is not None:
                async_to_sync(self._send_msg)(BROADCAST_CONNS, msg)
            else:
                LOG.error(f"Invalid message discarded {type=} {msg=}")
            sent_keys.add(msg)
        self._cleanup_cache(sent_keys)


# TODO put this somwehere else
NOTIFIER = Notifier()
NOTIFIER.start()
# NOTIFIER.join()
