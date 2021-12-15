"""Sends notifications to connections, reading from a queue."""
from logging import getLogger

from asgiref.sync import async_to_sync
from django.core.cache import cache

from codex.librarian.queue_mp import AdminNotifierTask, BroadcastNotifierTask
from codex.serializers.webpack import WEBSOCKET_MESSAGES as WS_MSGS
from codex.threads import AggregateMessageQueuedThread


LOG = getLogger(__name__)


class Notifier(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    NAME = "Notifier"
    WS_SEND_MSG = {"type": "websocket.send"}
    CONNS = {AdminNotifierTask: set(), BroadcastNotifierTask: set()}
    SUBSCRIBE_TYPES = {
        "register": BroadcastNotifierTask,
        "admin": AdminNotifierTask,
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

    def _aggregate_items(self, task):
        """Aggregate messages into cache."""
        self.cache[task.text] = task

    def _send_all_items(self):
        """Send all messages waiting in the message cache to client."""
        if not self.cache:
            return
        sent_keys = set()
        cache.clear()
        for text, task in self.cache.items():
            msg = WS_MSGS[text]
            send_msg = {"text": msg}
            send_msg.update(self.WS_SEND_MSG)
            conns = self.CONNS[task.__class__]
            async_to_sync(self._send_msg)(conns, send_msg)
            sent_keys.add(text)
        self._cleanup_cache(sent_keys)

    @classmethod
    def startup(cls):
        """Singleton thread create and start."""
        cls.thread = Notifier()
        cls.thread.start()

    @classmethod
    def shutdown(cls):
        """Shut down the thread and discard the connections."""
        cls.thread.stop()
        for type in cls.CONNS.keys():
            cls.CONNS[type] = set()
