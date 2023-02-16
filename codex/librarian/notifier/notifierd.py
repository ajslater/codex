"""Sends notifications to connections, reading from a queue."""
from time import time

from wsproto.frame_protocol import CloseReason

from codex.django_channels.consumers import ChannelGroups
from codex.threads import AggregateMessageQueuedThread


class NotifierThread(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    _EXPIRY = 60
    _WS_DISCONNECT_MESSAGE = {
        "type": "websocket_disconnect",
        "code": CloseReason.NORMAL_CLOSURE.value,
    }

    def __init__(self, broadcast_queue, *args, **kwargs):
        """Initialize local send url."""
        super().__init__(*args, **kwargs)
        self.broadcast_queue = broadcast_queue

    def aggregate_items(self, task):
        """Aggregate messages into cache."""
        self.cache[task.text] = task

    @classmethod
    def create_broadcast_item(cls, group, message):
        """Create a queue item for sending broadcast_group messages."""
        expiry = time() + cls._EXPIRY
        msg = {"type": "broadcast_group", "group": group.name, "message": message}
        item = (expiry, msg)
        return item

    def _group_send(self, group, message):
        """
        Send a group_send message to the mulitprocess broadcast channel.

        A random consumer awaiting the broadcast channel will consume it,
        and do a group_send with it's message.
        """
        item = self.create_broadcast_item(group, message)
        self.broadcast_queue.put(item)

    def send_all_items(self):
        """Send all messages waiting in the message cache to client."""
        if not self.cache:
            return
        sent_keys = set()
        for task in self.cache.values():
            try:
                group = task.type
                message = {
                    "type": "send_text",
                    "text": task.text,
                }
                self._group_send(group, message)
            except Exception as exc:
                self.log.exception(exc)

            sent_keys.add(task.text)
        self.cleanup_cache(sent_keys)

    def stop(self):
        """Send the consumer stop broadcast and stop the thread."""
        item = self.create_broadcast_item(
            ChannelGroups.ALL, self._WS_DISCONNECT_MESSAGE
        )
        self.broadcast_queue.put(item)
        self.broadcast_queue.close()
        self.broadcast_queue.join_thread()
        super().stop()
