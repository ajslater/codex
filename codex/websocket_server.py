"""Websocket Consumers."""
import random
import time

from logging import getLogger
from multiprocessing import Value
from queue import Queue
from threading import Thread

import simplejson as json

from asgiref.sync import async_to_sync
from django.core.cache import cache
from simplejson import JSONDecodeError


LOG = getLogger(__name__)

# Websocket Application
WS_ACCEPT_MSG = {"type": "websocket.accept"}
WS_SEND_MSG = {"type": "websocket.send"}
BROADCAST_CONNS = set()
UNSUBSCRIBE_MSG = "unsubscribe"
BROADCAST_MSG = "broadcast"
# Shared memory broadcast security
BROADCAST_SECRET = Value("i", random.randint(0, 100))
LIBRARY_CHANGED_MSG = "libraryChanged"
SCAN_ROOT_MSG = "scanLibrary"
WS_API_PATH = "api/v1/ws"

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


def is_ws_api_path(scope):
    """is this request on the url path we accept?"""
    path = scope.get("path")
    root_path = scope.get("root_path")
    short_path = path.lstrip(root_path)
    return short_path != WS_API_PATH and short_path != "/" + WS_API_PATH


async def websocket_application(scope, receive, send):
    """Set up broadcasts."""
    # if not is_ws_api_path(scope):
    #    return

    while True:
        event = await receive()

        if event["type"] == "websocket.connect":
            BROADCAST_CONNS.add(send)
            await send(WS_ACCEPT_MSG)

        if event["type"] == "websocket.disconnect":
            break

        if event["type"] == "websocket.receive":
            try:
                msg = json.loads(event["text"])
                msg_type = msg.get("type")
                message = msg.get("message")
                if msg_type == UNSUBSCRIBE_MSG:
                    BROADCAST_CONNS.remove(send)

                elif (
                    msg_type == BROADCAST_MSG
                    and msg.get("secret") == BROADCAST_SECRET.value
                ):
                    if message != SCAN_ROOT_MSG:
                        # flood control library changed messages
                        MESSAGE_QUEUE.put((message, time.time()))
                    else:
                        # don't flood control
                        for send in BROADCAST_CONNS:
                            # XXX can't tell who's an admin so send to
                            # everyone
                            send_msg = {"text": message}
                            send_msg.update(WS_SEND_MSG)
                            await send(send_msg)
            except JSONDecodeError as exc:
                LOG.error(exc)


def flood_control_worker():
    """
    Delay some broadcast messages for flood control.

    This thread runs in the main ASGI process to access the websockets.
    This lets other workers flood us with as many messages as they
    like and bottleneck them here in one spot before pinging the clients.

    May need to recognize different message types in the future.
    """
    LOG.info("Broadcast flood control worker started.")
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
    LOG.info("Broadcast flood control worker stopped.")


def start_flood_control_worker():
    """Start the flood control worker."""
    thread = Thread(
        target=flood_control_worker,
        name="websocket broadcast flood control worker",
        daemon=True,
    )
    thread.start()


def stop_flood_control_worker():
    """Make the thread end."""
    MESSAGE_QUEUE.put((SHUTDOWN_MSG, 0))
