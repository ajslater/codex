"""Websocket Server."""
import logging
import random
import time

from multiprocessing import Value
from queue import Queue
from threading import Thread

import simplejson as json

from asgiref.sync import async_to_sync
from django.core.cache import cache
from simplejson import JSONDecodeError

from codex.serializers.webpack import WEBSOCKET_MESSAGES


# TODO logging not configured for this app properly
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

# Flood control
MESSAGE_QUEUE = Queue()
SHUTDOWN_MSG = "shutdown"
FLOOD_DELAY = 2  # wait seconds before broadcasting
MAX_FLOOD_WAIT_TIME = 20


def get_send_msg(message):
    """Create a websocket send message."""
    msg = {"text": message}
    msg.update(WS_SEND_MSG)
    return msg


async def websocket_application(scope, receive, send):
    """Websocket application server."""
    LOG.debug(f"Starting websocket connection. {scope}")
    while True:
        event = await receive()

        if event["type"] == "websocket.connect":
            path = scope.get("path")
            if not path.endswith(IPC_SUFFIX):
                # The librarian doesn't care about broadcasts
                BROADCAST_CONNS.add(send)
            if path.endswith(ADMIN_SUFFIX):
                # Only admins care about admin messages
                ADMIN_CONNS.add(send)
            await send(WS_ACCEPT_MSG)

        if event["type"] == "websocket.disconnect":
            break

        if event["type"] == "websocket.receive":
            try:
                msg = json.loads(event["text"])
                msg_type = msg.get("type")
                message = msg.get("message")
                if (
                    msg_type == BROADCAST_MSG
                    and msg.get("secret") == BROADCAST_SECRET.value
                ):
                    if message in WEBSOCKET_MESSAGES["admin"]:
                        # don't flood control
                        for send in ADMIN_CONNS:
                            send_msg = {"text": message}
                            send_msg.update(WS_SEND_MSG)
                            await send(send_msg)
                    else:
                        # flood control library changed messages
                        MESSAGE_QUEUE.put((message, time.time()))

            except JSONDecodeError as exc:
                LOG.error(exc)
    LOG.debug("Closing websocket connection.")


def flood_control_worker():
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
                msg = {"text": message}
                msg.update(WS_SEND_MSG)
                for send in BROADCAST_CONNS:
                    async_to_sync(send)(msg)
            else:
                # put it back and wait
                if MESSAGE_QUEUE.empty():
                    MESSAGE_QUEUE.put((message, timestamp))
                    time.sleep(wait_left)
    LOG.info("Stopped Broadcast Flood Control Worker.")


def start_flood_control_worker():
    """Start the flood control worker."""
    thread = Thread(
        target=flood_control_worker,
        name="flood-control",
        daemon=True,
    )
    thread.start()


def stop_flood_control_worker():
    """Make the thread end."""
    MESSAGE_QUEUE.put((SHUTDOWN_MSG, 0))
