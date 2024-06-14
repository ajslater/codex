"""Sends notifications to connections, reading from a queue."""

from codex.threads import AggregateMessageQueuedThread


class NotifierThread(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    def __init__(self, broadcast_queue, *args, **kwargs):
        """Initialize local send url."""
        super().__init__(*args, **kwargs)
        self.broadcast_queue = broadcast_queue

    def aggregate_items(self, item):
        """Aggregate messages into cache."""
        self.cache[item.text] = item

    def _send_task(self, task):
        """Send a group_send message to the mulitprocess broadcast channel.

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

    def stop(self):
        """Send the consumer stop broadcast and stop the thread."""
        self.broadcast_queue.put(None)
        self.broadcast_queue.close()
        self.broadcast_queue.join_thread()
        super().stop()
