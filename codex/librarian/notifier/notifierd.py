"""Sends notifications to connections, reading from a queue."""
from urllib import request

from rest_framework.renderers import JSONRenderer

from codex.settings.settings import HYPERCORN_CONFIG
from codex.threads import AggregateMessageQueuedThread
from codex.serializers.websocket_send import SendSerializer


class NotifierThread(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    NAME = "Notifier"  # type: ignore
    URL = f"http://localhost:9810{HYPERCORN_CONFIG.root_path}/send"

    def aggregate_items(self, task):
        """Aggregate messages into cache."""
        self.cache[task.text] = task

    def _send_http(self, group, text):
        data_dict = {"group": group.value, "text": text}
        serializer = SendSerializer(data_dict)
        data = JSONRenderer().render(serializer.data)
        print("Notifier._send_http:", data)
        # TODO root_path

        rq = request.Request(self.URL, data=data)
        with request.urlopen(rq) as response:
            print("NotifierThread HTTP Response:", response.status, response.reason)

    def send_all_items(self):
        """Send all messages waiting in the message cache to client."""
        if not self.cache:
            return
        sent_keys = set()
        for task in self.cache.values():
            self._send_http(task.type, task.text)

            sent_keys.add(task.text)
        self.cleanup_cache(sent_keys)
