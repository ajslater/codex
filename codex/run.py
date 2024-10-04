#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""

import asyncio
import logging
from os import execv

from django.db import connection
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


def codex_startup():
    """Start up codex."""
    LOG.info(f"Starting Codex v{VERSION}")
    return codex_init()


def _database_checkpoint():
    """Write wal to disk and truncate it."""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    LOG.debug("checkpointed and truncated database wal")


def restart():
    """Restart this process."""
    from sys import argv

    print("Restarting Codex. Hold on to your butts...", flush=True)  # noqa: T201
    execv(__file__, argv)  # noqa: S606


def codex_shutdown(loggerd):
    """Shutdown for codex."""
    _database_checkpoint()
    LOG.info("Goodbye.")
    logging.shutdown()
    loggerd.stop()
    if RESTART_EVENT.is_set():
        restart()


def run():
    """Run Codex."""
    LOG.info(f"Running Codex v{VERSION}")
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
    if codex_startup():
        run()
    codex_shutdown(loggerd)


if __name__ == "__main__":
    main()
