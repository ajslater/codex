"""Global queue to send async queue messages to consumers from other processes."""

from multiprocessing import Queue

BROADCAST_QUEUE = Queue()
