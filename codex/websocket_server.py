"""Websocket Server."""
import json
import logging
import random
import time

from json import JSONDecodeError
from multiprocessing import Value
from queue import SimpleQueue
from threading import Thread

from asgiref.sync import async_to_sync
from django.core.cache import cache

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
MESSAGE_QUEUE = SimpleQueue()
SHUTDOWN_MSG = "shutdown"
FLOOD_DELAY = 2  # wait seconds before broadcasting
MAX_FLOOD_WAIT_TIME = 20


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
    while True:
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
                    message = msg.get("message")
                    # flood control library changed messages
                    MESSAGE_QUEUE.put((message, time.time()))
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
    LOG.debug("Closing websocket connection.")


class FloodControlThread(Thread):
    """Prevent floods of broadcast messages to clients."""

    thread = None
    SHUTDOWN_TIMEOUT = 5

    def __init__(self):
        """Init the thread."""
        super().__init__(name="flood-control", daemon=True)

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
            waiting_since = time.time()
            message, timestamp = MESSAGE_QUEUE.get()
            if message == SHUTDOWN_MSG:
                break
            wait_break = time.time() - waiting_since > MAX_FLOOD_WAIT_TIME
            if MESSAGE_QUEUE.empty() or wait_break:
                wait_left = timestamp + FLOOD_DELAY - time.time()
                if wait_left <= 0 or wait_break:
                    cache.clear()
                    async_to_sync(send_msg)(BROADCAST_CONNS, message)
                else:
                    # put it back and wait
                    if MESSAGE_QUEUE.empty():
                        MESSAGE_QUEUE.put((message, timestamp))
                        time.sleep(wait_left)
        LOG.info("Stopped Broadcast Flood Control Worker.")

    @classmethod
    def startup(cls):
        """Start the flood control worker."""
        cls.thread = FloodControlThread()
        cls.thread.start()

    @classmethod
    def shutdown(cls):
        """Make the thread end."""
        MESSAGE_QUEUE.put((SHUTDOWN_MSG, 0))
        if cls.thread:
            cls.thread.join(cls.SHUTDOWN_TIMEOUT)
