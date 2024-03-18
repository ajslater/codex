"""Global queue to send async queue messages to consumers from other processes."""

from aioprocessing import AioQueue

BROADCAST_QUEUE = AioQueue()
