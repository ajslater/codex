"""Sends notifications to connections, reading from a queue."""
from urllib import request

from rest_framework.renderers import JSONRenderer

from codex.serializers.websocket_send import SendSerializer
from codex.settings.settings import HYPERCORN_CONFIG, SECRET_KEY
from codex.threads import AggregateMessageQueuedThread


class NotifierThread(AggregateMessageQueuedThread):
    """Aggregates messages preventing floods and sends messages to clients."""

    @staticmethod
    def _get_bridge_url():
        """Determine the channels http bridge url."""
        host = "localhost"
        port = "9180"
        for bind in HYPERCORN_CONFIG.bind:
            host, port = bind.split(":")
            if host == "0.0.0.0":
                host = "localhost"
            if host != "localhost":
                # use the first non-localhost bind
                # but if there's only one bind, then use that.
                break
        prefix = HYPERCORN_CONFIG.root_path
        return f"http://{host}:{port}{prefix}/channels"

    def __init__(self, *args, **kwargs):
        """Initialize local send url."""
        super().__init__(*args, **kwargs)
        self._BRIDGE_URL = self._get_bridge_url()

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
        rq = request.Request(self._BRIDGE_URL, data=data)
        with request.urlopen(rq) as response:
            self.log.debug(
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
                self.log.exception(exc)

            sent_keys.add(task.text)
        self.cleanup_cache(sent_keys)
