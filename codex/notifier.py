"""
Sends notifications to connections, reading from a queue.
"""
from logging import getLogger

from asgiref.sync import async_to_sync
from django.core.cache import cache

from codex.threads import AggregateMessageQueuedThread


LOG = getLogger(__name__)


class NotifierMessage:
    """Timed message for flood control."""

    BROADCAST = 0
    ADMIN_BROADCAST = 1

    def __init__(self, type, message):
        """Set the message content."""
        self.type = type
        self.message = message


class Notifier(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    NAME = "UI-Notifier"
    WS_SEND_MSG = {"type": "websocket.send"}
    CONNS = {NotifierMessage.BROADCAST: set(), NotifierMessage.ADMIN_BROADCAST: set()}
    SUBSCRIBE_TYPES = {
        "register": NotifierMessage.BROADCAST,
        "admin": NotifierMessage.ADMIN_BROADCAST,
    }

    @classmethod
    def subscribe(cls, msg, send):
        """Subscribe or unsubscribe from a connection class."""
        for key, type in cls.SUBSCRIBE_TYPES.items():
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
