"""Custom channel layer."""
from asyncio import Queue
from queue import Empty

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
    def close_broadcast_queue():
        """Close up the broadcast queue."""
        try:
            while not BROADCAST_QUEUE.empty():  # type: ignore
                BROADCAST_QUEUE.get_nowait()  # type: ignore
        except Empty:
            pass
        BROADCAST_QUEUE.close()  # type: ignore
        BROADCAST_QUEUE.join_thread()  # type: ignore
