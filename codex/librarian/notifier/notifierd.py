"""Sends notifications to connections, reading from a queue."""

from typing_extensions import override

from codex.librarian.threads import AggregateMessageQueuedThread


class NotifierThread(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    def __init__(self, *args, broadcast_queue, **kwargs):
        """Initialize local send url."""
        self.broadcast_queue = broadcast_queue
        super().__init__(*args, **kwargs)

    @override
    def aggregate_items(self, item):
        """Aggregate messages into cache."""
        self.cache[item.text] = item

    def _send_task(self, task):
        """
        Send a group_send message to the mulitprocess broadcast channel.

        A random consumer awaiting the broadcast channel will consume it,
        and do a group_send with it's message.
        """
        item = {
            "group": task.group,
            "message": {
                "type": "send_text",
                "text": task.text,
            },
        }
        self.broadcast_queue.put(item)

    @override
    def send_all_items(self):
        """Send all messages waiting in the message cache to client."""
        if not self.cache:
            return
        sent_keys = set()
        for task in self.cache.values():
            try:
                self._send_task(task)
            except Exception:
                self.log.exception("Notifier send task")

            sent_keys.add(task.text)
        self.cleanup_cache(sent_keys)

    @override
    def stop(self):
        """Send the consumer stop broadcast and stop the thread."""
        self.broadcast_queue.put(None)
        self.broadcast_queue.close()
        self.broadcast_queue.join_thread()
        super().stop()
