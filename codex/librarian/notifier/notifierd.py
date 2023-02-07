"""Sends notifications to connections, reading from a queue."""
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer

from codex.serializers.choices import WEBSOCKET_MESSAGES as WS_MSGS
from codex.threads import AggregateMessageQueuedThread


class NotifierThread(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    NAME = "Notifier"  # type: ignore

    def aggregate_items(self, task):
        """Aggregate messages into cache."""
        self.cache[task.text] = task

    def send_all_items(self):
        """Send all messages waiting in the message cache to client."""
        if not self.cache:
            return
        sent_keys = set()
        for task in self.cache.values():
            layer = get_channel_layer()
            if not layer:
                return
            msg = WS_MSGS.get(task.text)
            if not msg:
                return
            send_msg = {"text": msg}
            sync_to_async(layer.group_send)(task.type.name, send_msg)
            sent_keys.add(task.text)
        self.cleanup_cache(sent_keys)
