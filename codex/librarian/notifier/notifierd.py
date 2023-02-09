"""Sends notifications to connections, reading from a queue."""
from urllib import request

from rest_framework.renderers import JSONRenderer

from codex.serializers.websocket_send import SendSerializer
from codex.settings.settings import HYPERCORN_CONFIG, SECRET_KEY
from codex.threads import AggregateMessageQueuedThread


class NotifierThread(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    NAME = "Notifier"  # type: ignore
    URL = f"http://localhost:9810{HYPERCORN_CONFIG.root_path}/send"

    def aggregate_items(self, task):
        """Aggregate messages into cache."""
        self.cache[task.text] = task

    @staticmethod
    def _render_message(group, text):
        data_dict = {"group": group.value, "text": text, "secret_key": SECRET_KEY}
        serializer = SendSerializer(data_dict)
        return JSONRenderer().render(serializer.data)

    def _send_http(self, group, text):
        data = self._render_message(group, text)
        rq = request.Request(self.URL, data=data)
        with request.urlopen(rq) as response:
            self.logger.debug(
                f"NotifierThread HTTP Response: {response.status} {response.reason}"
            )

    def send_all_items(self):
        """Send all messages waiting in the message cache to client."""
        if not self.cache:
            return
        sent_keys = set()
        for task in self.cache.values():
            try:
                self._send_http(task.type, task.text)
            except Exception as exc:
                self.logger.exception(exc)

            sent_keys.add(task.text)
        self.cleanup_cache(sent_keys)
