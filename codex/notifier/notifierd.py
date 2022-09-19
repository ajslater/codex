"""Sends notifications to connections, reading from a queue."""
import asyncio

from asgiref.sync import async_to_sync

from codex.notifier.tasks import Channels
from codex.serializers.choices import WEBSOCKET_MESSAGES as WS_MSGS
from codex.settings.logging import get_logger
from codex.threads import AggregateMessageQueuedThread


LOG = get_logger(__name__)


class Notifier(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    NAME = "Notifier"  # type: ignore
    WS_SEND_MSG = {"type": "websocket.send"}
    CONNS = dict([(channel, set()) for channel in Channels])

    @classmethod
    def subscribe(cls, msg, send):
        """Subscribe or unsubscribe from a connection class."""
        if msg.get("admin"):
            key = Channels.ADMIN
        else:
            key = Channels.ALL

        conns = cls.CONNS.get(key)
        if conns is None:
            LOG.warning(f"No socket conn set found for {key}")
            return

        if msg.get("register"):
            conns.add(send)
        else:
            conns.discard(send)

    @staticmethod
    async def _send_msg(conns, send_msg):
        """Send message to all connections."""
        for send in conns:
            try:
                await send(send_msg)
                await asyncio.sleep(0)
            except Exception as exc:
                LOG.warning(f"Error in {Notifier.NAME}._send_msg {send_msg} {exc}")

    def aggregate_items(self, task):
        """Aggregate messages into cache."""
        self.cache[task.text] = task

    def send_all_items(self):
        """Send all messages waiting in the message cache to client."""
        if not self.cache:
            return
        sent_keys = set()
        for text, task in self.cache.items():
            msg = WS_MSGS[text]
            send_msg = {"text": msg}
            send_msg.update(self.WS_SEND_MSG)
            conns = self.CONNS.get(Channels.ALL, set())
            if task.type == Channels.ADMIN:
                conns |= self.CONNS.get(Channels.ADMIN, set())
            async_to_sync(self._send_msg)(conns, send_msg)
            sent_keys.add(text)
        self.cleanup_cache(sent_keys)

    @classmethod
    def startup(cls):
        """Singleton thread create and start."""
        cls.thread = Notifier()
        cls.thread.start()

    @classmethod
    def shutdown(cls):
        """Shut down the thread and discard the connections."""
        if not cls.thread:
            LOG.warning(f"Cannot shutdown {cls.NAME} that hasn't started.")
            return
        cls.thread.stop()
        cls.thread.join()
        for type in cls.CONNS.keys():
            cls.CONNS[type] = set()
        cls.thread = None
