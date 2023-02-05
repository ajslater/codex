"""Sends notifications to connections, reading from a queue."""
import asyncio

from asgiref.sync import async_to_sync

from codex.notifier.tasks import Channels, NotifierSubscribeTask
from codex.serializers.choices import WEBSOCKET_MESSAGES as WS_MSGS
from codex.threads import AggregateMessageQueuedThread


class Notifier(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    NAME = "Notifier"  # type: ignore
    WS_SEND_MSG = {"type": "websocket.send"}

    def __init__(self, *args, **kwargs):
        """Initialize Conns."""
        super().__init__(*args, **kwargs)
        self.conns = dict([(channel, set()) for channel in Channels])

    def _subscribe(self, msg, send):
        """Subscribe or unsubscribe from a connection class."""
        if msg.get("admin"):
            key = Channels.ADMIN
        else:
            key = Channels.ALL

        conns = self.conns.get(key)
        if conns is None:
            self.logger.warning(f"No socket conn set found for {key}")
            return

        if msg.get("register"):
            self.logger.debug("Notifier.subscribe", send)
            conns.add(send)
        else:
            self._unsubscribe(send)

    def _unsubscribe(self, send):
        """Unsub from all conns."""
        self.logger.debug("Notifier.unsubscribe", send)
        for conn in self.conns.values():
            conn.discard(send)

    async def _send_msg(self, conns, send_msg):
        """Send message to all connections."""
        bad_conns = set()
        for send in conns:
            try:
                await send(send_msg)
                await asyncio.sleep(0)
            except Exception as exc:
                self.logger.warning(f"{Notifier.NAME}._send_msg {exc}")
                self.logger.debug(f"Message was {send_msg}")
                bad_conns.add(send)
        if bad_conns:
            for bad_conn in bad_conns:
                self._unsubscribe(bad_conn)

    def aggregate_items(self, task):
        """Aggregate messages into cache."""
        if isinstance(NotifierSubscribeTask, task):
            if task.subscribe:
                self._subscribe(task.text, task.send)
            else:
                self._unsubscribe(task.send)
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
            conns = self.conns.get(Channels.ALL, set())
            if task.type == Channels.ADMIN:
                conns |= self.conns.get(Channels.ADMIN, set())
            async_to_sync(self._send_msg)(conns, send_msg)
            sent_keys.add(text)
        self.cleanup_cache(sent_keys)

    # @classmethod
    # def startup(cls):
    #    """Singleton thread create and start."""
    #    cls.thread = Notifier(log_queue=LOG_QUEUE)
    #    cls.thread.start()

    # @classmethod
    # def shutdown(cls):
    #    """Shut down the thread and discard the connections."""
    #    if not cls.thread:
    #        logger = get_logger(__name__)
    #        logger.warning(f"Cannot shutdown {cls.NAME} that hasn't started.")
    #        return
    #    cls.thread.stop()
    #    cls.thread.join()
    #    cls.thread = None
