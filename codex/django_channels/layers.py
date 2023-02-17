"""Custom channel layer."""
from asyncio import Queue
from queue import Empty
from time import time

from channels.layers import InMemoryChannelLayer

from codex.django_channels.broadcast_queue import BROADCAST_QUEUE


BROADCAST_CHANNEL_NAME = "broadcast"


class CodexChannelLayer(InMemoryChannelLayer):
    """
    Codex In-memory channel layer implementation.

    Works with a special AioQueue broadcast channel.
    """

    async def receive(self, channel):
        """
        Receive the first message that arrives on the channel.

        If more than one coroutine waits on the same channel, a random one
        of the waiting coroutines will get the result.
        """
        assert self.valid_channel_name(channel)
        self._clean_expired()

        # Do a plain direct receive
        if channel == BROADCAST_CHANNEL_NAME:
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
        if channel == BROADCAST_CHANNEL_NAME:
            private_queue = queue.queue
        else:
            private_queue = queue._queue

        return private_queue[0][0] >= time()

    def _clean_expired(self):
        """
        Goes through all messages and groups and removes those that are expired.

        Any channel with an expired message is removed from all groups.
        """
        # Channel cleanup
        for channel, queue in list(self.channels.items()):
            # See if it's expired
            while not queue.empty():
                if self._queue_peek_expired(channel, queue):
                    break
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
