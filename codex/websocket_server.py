"""Websocket Server."""
import json
import logging
import time

from json import JSONDecodeError
from queue import Empty

from asgiref.sync import async_to_sync
from django.core.cache import cache

from codex.queued_worker import QueuedWorker, TimedMessage
from codex.settings.django_setup import django_setup


django_setup()

LOG = logging.getLogger(__name__)

# Websocket Application
WS_ACCEPT_MSG = {"type": "websocket.accept"}
WS_SEND_MSG = {"type": "websocket.send"}
BROADCAST_CONNS = set()
ADMIN_CONNS = set()


async def _send_msg(conns, text):
    """Construct a ws send message and send to all connections."""
    # text = WEBSOCKET_API[message]
    _send_msg = {"text": text}
    _send_msg.update(WS_SEND_MSG)
    for send in conns:
        await send(_send_msg)


async def websocket_application(scope, receive, send):
    """Websocket application server."""
    LOG.debug(f"Starting websocket connection. {scope}")
    NOTIFIER.start()
    while True:
        try:
            event = await receive()

            if event["type"] == "websocket.connect":
                await send(WS_ACCEPT_MSG)

            if event["type"] == "websocket.disconnect":
                break

            if event["type"] == "websocket.receive":
                try:
                    msg = json.loads(event["text"])
                    msg_type = msg.get("type")

                    if (msg_type) == "subscribe":
                        if msg.get("register"):
                            # The librarian doesn't care about broadcasts
                            BROADCAST_CONNS.add(send)
                        else:
                            BROADCAST_CONNS.discard(send)

                        if msg.get("admin"):
                            # Only admins care about admin messages
                            ADMIN_CONNS.add(send)
                        else:
                            ADMIN_CONNS.discard(send)
                    else:
                        LOG.warning(f"Bad message type to websockets: {msg_type}")

                except JSONDecodeError as exc:
                    LOG.error(exc)
        except Exception as exc:
            LOG.exception(exc)
    NOTIFIER.join()
    LOG.debug("Closing websocket connection.")


class NotifierMessage(TimedMessage):
    """Timed message for flood control."""

    BROADCAST = 0
    ADMIN_BROADCAST = 1

    def __init__(self, type, message):
        """Set the message content."""
        self.type = type
        self.message = message
        super().__init__()


class NotificiationWorker(QueuedWorker):
    """Prevent floods of broadcast messages to clients."""

    NAME = "ui-notifier"
    FLOOD_DELAY = 2  # wait seconds before broadcasting
    MAX_FLOOD_WAIT_TIME = 20

    def __init__(self, *args, **kwargs):
        self.messages = {}
        super().__init__(*args, **kwargs)

    def run(self):
        """
        Delay some broadcast messages for flood control.

        This thread runs in the main ASGI process to access the websockets.
        This lets other workers flood us with as many messages as they
        like and bottleneck them here in one spot before pinging the clients.
        """
        LOG.info("Started Notification Worker.")
        waiting_since = time.time()
        while True:
            try:
                try:
                    message = self.queue.get(timeout=self.FLOOD_DELAY)
                    if message == self.SHUTDOWN_MSG:
                        break
                    self.messages[message.message] = message.type
                    wait_break = time.time() - waiting_since > self.MAX_FLOOD_WAIT_TIME
                    if not wait_break:
                        continue
                except Empty:
                    pass
                # send all stored messages to the frontend
                if self.messages:
                    cache.clear()
                    for msg, type in self.messages.items():
                        if type == NotifierMessage.BROADCAST:
                            async_to_sync(_send_msg)(BROADCAST_CONNS, msg)
                        elif type == NotifierMessage.ADMIN_BROADCAST:
                            async_to_sync(_send_msg)(ADMIN_CONNS, msg)
                        else:
                            LOG.error(f"invalid message type {type} for message {msg}")
                    self.messages = {}
                waiting_since = time.time()
            except Exception as exc:
                LOG.exception(exc)
        LOG.info("Stopped Notification Worker.")


NOTIFIER = NotificiationWorker()
