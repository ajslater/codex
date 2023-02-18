"""Custom channel layer."""
from asyncio import Queue
from copy import deepcopy
from queue import Empty
from time import time

from channels.layers import ChannelFull, InMemoryChannelLayer

from codex.django_channels.broadcast_queue import BROADCAST_QUEUE

BROADCAST_CHANNEL_NAME = "broadcast"


class CodexChannelLayer(InMemoryChannelLayer):
    """Codex In-memory channel layer implementation.

    Works with a special AioQueue broadcast channel.
    """

    async def send(self, channel, message):
        """Send a message onto a (general or specific) channel."""
        # Typecheck
        assert isinstance(message, dict), "message is not a dict"
        assert self.valid_channel_name(channel), "Channel name not valid"
        # If it's a process-local channel, strip off local part and stick full
        # name in message
        assert "__asgi_channel__" not in message

        is_aio_queue = channel == BROADCAST_CHANNEL_NAME

        if is_aio_queue:
            queue = self.channels.setdefault(channel, BROADCAST_QUEUE)
        else:
            queue = self.channels.setdefault(channel, Queue())
        # Are we full
        if queue.qsize() >= self.capacity:
            raise ChannelFull(channel)

        # Add message
        item = (time() + self.expiry, deepcopy(message))
        if is_aio_queue:
            await queue.coro_put(item)
        else:
            await queue.put(item)

    async def receive(self, channel):
        """Receive the first message that arrives on the channel.

        If more than one coroutine waits on the same channel, a random one
        of the waiting coroutines will get the result.
        """
        assert self.valid_channel_name(channel)
        self._clean_expired()

        is_aio_queue = channel == BROADCAST_CHANNEL_NAME

        # Do a plain direct receive
        if is_aio_queue:
            # broadcast channel uses the singleton AioQueue
            queue = self.channels.setdefault(channel, BROADCAST_QUEUE)
            _, message = await queue.coro_get()  # type: ignore
        else:
            queue = self.channels.setdefault(channel, Queue())
            try:
                _, message = await queue.get()
            finally:
                if queue.empty():
                    del self.channels[channel]

        return message

    @staticmethod
    def _queue_peek_expired(channel, queue):
        """Peek for expired message by queue type."""
        if queue.empty():
            return False

        is_aio_queue = channel == BROADCAST_CHANNEL_NAME
        if is_aio_queue:
            private_queue = queue._obj._buffer
        else:
            private_queue = queue._queue

        expired = False
        try:
            expired = private_queue[0][0] >= time()
        except Exception:
            # TODO Fix
            print("PEEK EXCEPTION", channel, private_queue[0])
        return expired

    def _clean_expired(self):
        """Goes through all messages and groups and removes those that are expired.

        Any channel with an expired message is removed from all groups.
        """
        # Channel cleanup
        for channel, queue in list(self.channels.items()):
            # See if it's expired
            while self._queue_peek_expired(channel, queue):
                queue.get_nowait()
                # Any removal prompts group discard
                self._remove_from_groups(channel)
                # Is the channel now empty and needs deleting?
                if queue.empty():
                    del self.channels[channel]

        # Group Expiration
        timeout = int(time()) - self.group_expiry
        for group in self.groups:
            for channel in list(self.groups.get(group, set())):
                # If join time is older than group_expiry end the group membership
                if (
                    self.groups[group][channel]
                    and int(self.groups[group][channel]) < timeout
                ):
                    # Delete from group
                    del self.groups[group][channel]

    @staticmethod
    def close_broadcast_queue():
        """Close up the broadcast queue."""
        try:
            while not BROADCAST_QUEUE.empty():  # type: ignore
                BROADCAST_QUEUE.get_nowait()  # type: ignore
        except Empty:
            pass
        BROADCAST_QUEUE.close()  # type: ignore
        BROADCAST_QUEUE.join_thread()  # type: ignore
