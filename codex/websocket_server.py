"""Websocket Server."""
import json
import logging

from json import JSONDecodeError

from asgiref.sync import async_to_sync
from django.core.cache import cache

from codex.threads import AggregateMessageQueuedThread


LOG = logging.getLogger(__name__)
WS_ACCEPT_MSG = {"type": "websocket.accept"}


class NotifierMessage:
    """Timed message for flood control."""

    BROADCAST = 0
    ADMIN_BROADCAST = 1

    def __init__(self, type, message):
        """Set the message content."""
        self.type = type
        self.message = message


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
                        Notifier.subscribe(
                            NotifierMessage.BROADCAST, "register", msg, send
                        )
                        Notifier.subscribe(
                            NotifierMessage.ADMIN_BROADCAST, "admin", msg, send
                        )
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


class Notifier(AggregateMessageQueuedThread):
    """Prevent floods of broadcast messages to clients."""

    NAME = "UI-Notifier"
    WS_SEND_MSG = {"type": "websocket.send"}
    CONNS = {}

    @classmethod
    def subscribe(cls, type, key, msg, send):
        """Subscribe or unsubscribe from a connection class."""
        if type not in cls.CONNS:
            cls.CONNS[type] = set()
        conns = cls.CONNS[type]
        if msg.get(key):
            conns.add(send)
        else:
            conns.discard(send)

    @staticmethod
    async def _send_msg(conns, send_msg):
        """Send message to all connections."""
        for send in conns:
            await send(send_msg)

    def _aggregate_items(self, message):
        """Aggregate messages into cache."""
        self.cache[message.message] = message

    def _send_all_items(self):
        """Send all messages waiting in the message cache to client."""
        if not self.cache:
            return
        sent_keys = set()
        cache.clear()
        for msg, message in self.cache.items():
            if self._do_send_item(msg):
                send_msg = {"text": message.message}
                send_msg.update(self.WS_SEND_MSG)
                conns = self.CONNS[message.type]
                async_to_sync(self._send_msg)(conns, send_msg)
            sent_keys.add(msg)
        self._cleanup_cache(sent_keys)

    @classmethod
    def startup(cls):
        cls.thread = Notifier()
        cls.thread.start()

    @classmethod
    def shutdown(cls):
        cls.thread.join()
        cls.CONNS = {}
