#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""

import asyncio
from os import execv

from django.db import connection
from hypercorn.asyncio import serve
from loguru import logger

from codex.asgi import application
from codex.librarian.librariand import LibrarianDaemon
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.settings import HYPERCORN_CONFIG
from codex.signals.os_signals import RESTART_EVENT, SHUTDOWN_EVENT
from codex.startup import codex_init
from codex.startup.logger_init import init_logging
from codex.version import VERSION
from codex.websockets.aio_queue import BROADCAST_QUEUE


def codex_startup():
    """Start up codex."""
    logger.info(f"Starting Codex v{VERSION}")
    return codex_init()


def _database_checkpoint():
    """Write wal to disk and truncate it."""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    logger.debug("checkpointed and truncated database wal")


def restart():
    """Restart this process."""
    from sys import argv

    print("Restarting Codex. Hold on to your butts...", flush=True)  # noqa: T201
    execv(__file__, argv)  # noqa: S606


def codex_shutdown():
    """Shutdown for codex."""
    _database_checkpoint()
    logger.success("Goodbye.")
    logger.complete()
    if RESTART_EVENT.is_set():
        restart()


def run():
    """Run Codex."""
    logger.success(f"Running Codex v{VERSION}")
    librarian = LibrarianDaemon(logger, LIBRARIAN_QUEUE, BROADCAST_QUEUE)
    librarian.start()
    asyncio.run(
        serve(
            application,  # pyright: ignore[reportArgumentType]
            HYPERCORN_CONFIG,
            shutdown_trigger=SHUTDOWN_EVENT.wait,
        )
    )
    librarian.stop()


def main():
    """Set up and run Codex."""
    init_logging()
    if codex_startup():
        run()
    codex_shutdown()


if __name__ == "__main__":
    main()
