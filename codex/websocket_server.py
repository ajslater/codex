"""Websocket Server."""
import json
import logging
import random
import time

from json import JSONDecodeError
from multiprocessing import Value

from asgiref.sync import async_to_sync
from django.core.cache import cache

from codex.buffer_thread import BufferThread, TimedMessage
from codex.settings.django_setup import django_setup


django_setup()

LOG = logging.getLogger(__name__)

# Websocket Application
WS_ACCEPT_MSG = {"type": "websocket.accept"}
WS_SEND_MSG = {"type": "websocket.send"}
BROADCAST_CONNS = set()
ADMIN_CONNS = set()
BROADCAST_MSG = "broadcast"
# Shared memory broadcast security
BROADCAST_SECRET = Value("i", random.randint(0, 100))
WS_API_PATH = "api/v1/ws"
ADMIN_SUFFIX = "/a"
IPC_SUFFIX = "/ipc"
IPC_URL_TMPL = "ws://localhost:{port}/" + WS_API_PATH + IPC_SUFFIX

# Flood control


class MessageType:
    """Types of messages."""

    SUBSCRIBE = "subscribe"
    BROADCAST = "broadcast"
    ADMIN_BROADCAST = "admin_broadcast"
    SECRET_TYPES = set([BROADCAST, ADMIN_BROADCAST])


async def send_msg(conns, text):
    """Construct a ws send message and send to all connections."""
    # text = WEBSOCKET_API[message]
    _send_msg = {"text": text}
    _send_msg.update(WS_SEND_MSG)
    for send in conns:
        await send(_send_msg)


async def websocket_application(scope, receive, send):
    """Websocket application server."""
    LOG.debug(f"Starting websocket connection. {scope}")
    flood_control_thread = FloodControlThread()
    flood_control_thread.start()
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
                    # msg_message = msg.get("message")

                    if (msg_type) == MessageType.SUBSCRIBE:

                        if msg.get("register"):
                            # The librarian doesn't care about broadcasts
                            BROADCAST_CONNS.add(send)
                        else:
                            BROADCAST_CONNS.discard(send)
                            ADMIN_CONNS.discard(send)

                        if msg.get("admin"):
                            # Only admins care about admin messages
                            ADMIN_CONNS.add(send)
                        else:
                            ADMIN_CONNS.discard(send)
                    elif (
                        msg_type == MessageType.BROADCAST
                        and msg.get("secret") == BROADCAST_SECRET.value
                    ):
                        message = FloodControlMessage(msg.get("message"))
                        # flood control library changed messages
                        flood_control_thread.queue.put(message)
                    elif (
                        msg_type == MessageType.ADMIN_BROADCAST
                        and msg.get("secret") == BROADCAST_SECRET.value
                    ):
                        message = msg.get("message")
                        await send_msg(ADMIN_CONNS, message)
                    else:
                        # Keepalive?
                        pass

                except JSONDecodeError as exc:
                    LOG.error(exc)
        except Exception as exc:
            LOG.exception(exc)
    flood_control_thread.join()
    LOG.debug("Closing websocket connection.")


class FloodControlMessage(TimedMessage):
    """Timed message for flood control."""

    def __init__(self, message):
        """Set the message content."""
        self.message = message
        super().__init__()


class FloodControlThread(BufferThread):
    """Prevent floods of broadcast messages to clients."""

    NAME = "ui-notification-flood-control"
    FLOOD_DELAY = 2  # wait seconds before broadcasting
    MAX_FLOOD_WAIT_TIME = 20

    def run(self):
        """
        Delay some broadcast messages for flood control.

        This thread runs in the main ASGI process to access the websockets.
        This lets other workers flood us with as many messages as they
        like and bottleneck them here in one spot before pinging the clients.

        May need to recognize different message types in the future.
        """
        LOG.info("Started Broadcast Flood Control Worker.")
        while True:
            try:
                waiting_since = time.time()
                message = self.queue.get()
                if message == self.SHUTDOWN_MSG:
                    break
                wait_break = time.time() - waiting_since > self.MAX_FLOOD_WAIT_TIME
                if not self.queue.empty() and not wait_break:
                    # discard message
                    continue
                wait_left = message.time + self.FLOOD_DELAY - time.time()
                if wait_left <= 0 or wait_break:
                    # send it to the frontend
                    cache.clear()
                    async_to_sync(send_msg)(BROADCAST_CONNS, message.message)
                else:
                    # put it back and wait
                    self.queue.put(message)
                    time.sleep(wait_left)
            except Exception as exc:
                LOG.exception(exc)
        LOG.info("Stopped Broadcast Flood Control Worker.")
