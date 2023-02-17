#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""
import asyncio
import threading

from multiprocessing import set_start_method
from os import execv

from hypercorn.asyncio import serve

from codex.asgi import application
from codex.django_channels.broadcast_queue import BROADCAST_QUEUE
from codex.django_channels.layers import CodexChannelLayer
from codex.librarian.librariand import LibrarianDaemon
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.loggerd import CodexLogQueueListener
from codex.logger.logging import get_logger
from codex.logger.mp_queue import LOG_QUEUE
from codex.settings.settings import HYPERCORN_CONFIG
from codex.signals.os_signals import RESTART_EVENT, SHUTDOWN_EVENT
from codex.startup import codex_init
from codex.version import VERSION


LOG = get_logger(__name__)


def restart():
    """Restart this process."""
    from sys import argv

    print("Restarting Codex. Hold on to your butts...", flush=True)
    execv(__file__, argv)  # nosec


def run():
    """Run Codex."""
    librarian = LibrarianDaemon(LIBRARIAN_QUEUE, LOG_QUEUE, BROADCAST_QUEUE)
    librarian.start()
    asyncio.run(
        serve(
            application,
            HYPERCORN_CONFIG,
            shutdown_trigger=SHUTDOWN_EVENT.wait,  # type: ignore
        )
    )
    CodexChannelLayer.close_broadcast_queue()
    librarian.stop()


def _release_thread_locks():
    """
    Release leaked, stuck thread locks.

    For an unknown reason more than one simultaneous consumer leads to
    a thread deadlocking situation. The threads hang and prevent codex
    from exiting.
    """
    released = 0
    for thread in threading.enumerate():
        if thread.name.startswith("ThreadPoolExecutor"):
            thread._tstate_lock.release()  # type: ignore
            thread._stop()  # type: ignore
            released += 1
    if released:
        LOG.debug(f"Released {released} locked threads.")


def main():
    """Set up and run Codex."""
    loggerd = CodexLogQueueListener(LOG_QUEUE)
    loggerd.start()
    LOG.info(f"Running Codex v{VERSION}")
    codex_init()
    run()
    _release_thread_locks()
    LOG.info("Goodbye.")
    loggerd.stop()
    if RESTART_EVENT.is_set():
        restart()


if __name__ == "__main__":
    set_start_method("spawn", force=True)
    main()
