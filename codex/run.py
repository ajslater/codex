#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""
import asyncio
from multiprocessing import set_start_method
from os import execv

from hypercorn.asyncio import serve

from codex.asgi import application
from codex.librarian.librariand import LibrarianDaemon
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.loggerd import CodexLogQueueListener
from codex.logger.logging import get_logger
from codex.logger.mp_queue import LOG_QUEUE
from codex.settings.settings import HYPERCORN_CONFIG
from codex.signals.os_signals import RESTART_EVENT, SHUTDOWN_EVENT
from codex.startup import codex_init
from codex.version import VERSION
from codex.websockets.aio_queue import BROADCAST_QUEUE

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
    librarian.stop()


def main():
    """Set up and run Codex."""
    loggerd = CodexLogQueueListener(LOG_QUEUE)
    loggerd.start()
    LOG.info(f"Running Codex v{VERSION}")
    codex_init()
    run()
    LOG.info("Goodbye.")
    loggerd.stop()
    if RESTART_EVENT.is_set():
        restart()


if __name__ == "__main__":
    set_start_method("spawn", force=True)
    main()
