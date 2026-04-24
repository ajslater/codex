#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs granian."""

import asyncio
from os import execv

from django.db import connection
from granian.constants import HTTPModes, Interfaces
from granian.server.embed import Server
from loguru import logger
from setproctitle import setproctitle

from codex.asgi import application
from codex.librarian.librariand import LibrarianDaemon
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.settings import (
    GRANIAN_HOST,
    GRANIAN_HTTP,
    GRANIAN_PORT,
    GRANIAN_URL_PATH_PREFIX,
    GRANIAN_WEBSOCKETS,
    WATCH_FOR_CHANGES,
)
from codex.signals.os_signals import RESTART_EVENT, SHUTDOWN_EVENT
from codex.startup import codex_init
from codex.startup.loguru import loguru_init
from codex.version import PACKAGE_NAME, VERSION
from codex.websockets.mp_queue import BROADCAST_QUEUE


def codex_startup() -> bool:
    """Start up codex."""
    logger.info(f"Starting Codex v{VERSION}")
    return codex_init()


def _database_checkpoint() -> None:
    """Write wal to disk and truncate it."""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    logger.debug("checkpointed and truncated database wal")


def restart() -> None:
    """Restart this process."""
    from sys import argv

    print("Restarting Codex. Hold on to your butts...", flush=True)  # noqa: T201
    execv(__file__, argv)  # noqa: S606


def codex_shutdown() -> None:
    """Shutdown for codex."""
    _database_checkpoint()
    logger.success("Goodbye.")
    logger.complete()
    if RESTART_EVENT.is_set():
        restart()


def _build_server() -> Server:
    """
    Build the granian embedded server.

    Note: the embed server runs workers as asyncio tasks (single-worker only),
    which lets us integrate cleanly with the SHUTDOWN_EVENT lifecycle.
    """
    return Server(
        application,
        interface=Interfaces.ASGI,
        address=GRANIAN_HOST,
        port=GRANIAN_PORT,
        websockets=GRANIAN_WEBSOCKETS,
        http=HTTPModes(GRANIAN_HTTP),
        url_path_prefix=GRANIAN_URL_PATH_PREFIX,
    )


async def _watch_for_changes() -> None:
    """Watch source files and trigger restart on changes."""
    from watchfiles import awatch

    async for _changes in awatch("codex"):
        logger.info("File changes detected, restarting...")
        RESTART_EVENT.set()
        SHUTDOWN_EVENT.set()
        break


async def _serve(server: Server) -> None:
    """Run granian until SHUTDOWN_EVENT fires, then stop gracefully."""
    server_task = asyncio.create_task(server.serve())
    if WATCH_FOR_CHANGES:
        watch_task = asyncio.create_task(_watch_for_changes())
    else:
        watch_task = None
    await SHUTDOWN_EVENT.wait()
    server.stop()
    await server_task
    if watch_task:
        await watch_task


def run() -> None:
    """Run Codex."""
    logger.success(f"Running Codex v{VERSION}")
    librarian = LibrarianDaemon(logger, LIBRARIAN_QUEUE, BROADCAST_QUEUE)
    librarian.start()
    server = _build_server()
    asyncio.run(_serve(server))
    librarian.stop()


def main() -> None:
    """Set up and run Codex."""
    logger.debug(f"Starting {PACKAGE_NAME}")
    setproctitle(PACKAGE_NAME)
    loguru_init()
    if codex_startup():
        run()
    codex_shutdown()


if __name__ == "__main__":
    main()
