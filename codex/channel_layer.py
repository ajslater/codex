# from asyncio import Queue

# from aioprocessing import AioQueue as Queue
import asyncio
import time

from channels.layers import InMemoryChannelLayer


# from janus import Queue  # <-- move notifier to main process.


# from multiprocessing import Queue


class CodexChannelLayer(InMemoryChannelLayer):
    """
    In-memory channel layer implementation
    """

    # BROADCAST_QUEUE = Queue()
    BROADCAST_CHANNEL_NAME = "broadcast"

    # def __init__(self, **kwargs):
    #    super().__init__(**kwargs)
    #    self.valid_channel_name(self.BROADCAST_CHANNEL_NAME)
    #    self.channels["broadcast"] = self.BROADCAST_QUEUE

    async def receive(self, channel):
        """
        Receive the first message that arrives on the channel.
        If more than one coroutine waits on the same channel, a random one
        of the waiting coroutines will get the result.
        """
        assert self.valid_channel_name(channel)
        self._clean_expired()

        queue = self.channels.setdefault(channel, asyncio.Queue())

        # Do a plain direct receive
        if channel == self.BROADCAST_CHANNEL_NAME:
            _, message = await queue.coro_get()
        else:
            try:
                _, message = await queue.get()
            finally:
                if queue.empty():
                    del self.channels[channel]

        return message

    def _clean_expired(self):
        """
        Goes through all messages and groups and removes those that are expired.
        Any channel with an expired message is removed from all groups.
        """
        # Channel cleanup
        for channel, queue in list(self.channels.items()):
            if channel == self.BROADCAST_CHANNEL_NAME:
                continue
            # See if it's expired
            while not queue.empty() and queue._queue[0][0] < time.time():
                queue.get_nowait()
                # Any removal prompts group discard
                self._remove_from_groups(channel)
                # Is the channel now empty and needs deleting?
                if queue.empty():
                    del self.channels[channel]

        # Group Expiration
        timeout = int(time.time()) - self.group_expiry
        for group in self.groups:
            for channel in list(self.groups.get(group, set())):
                # If join time is older than group_expiry end the group membership
                if (
                    self.groups[group][channel]
                    and int(self.groups[group][channel]) < timeout
                ):
                    # Delete from group
                    del self.groups[group][channel]
