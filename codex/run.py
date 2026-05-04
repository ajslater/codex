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


def _raise_fd_limit() -> None:
    """
    Raise RLIMIT_NOFILE soft limit toward the hard cap.

    macOS ships a 256 soft cap for RLIMIT_NOFILE which a cold burst of ~100
    parallel cover requests can easily exhaust: each Django thread keeps a
    sticky SQLite connection (CONN_MAX_AGE=600) and SQLite WAL mode opens
    3 FDs per connection (main + -wal + -shm). Bumping the soft limit is a
    non-invasive equivalent to running with ``ulimit -Sn 8192``.
    No-op on platforms without the resource module (e.g. Windows).
    """
    try:
        import resource
    except ImportError:
        return
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = 8192 if hard == resource.RLIM_INFINITY else min(hard, 8192)
    if soft >= target:
        return
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
    except (OSError, ValueError) as exc:
        logger.warning(f"Could not raise RLIMIT_NOFILE from {soft}: {exc}")
        return
    logger.debug(f"Raised RLIMIT_NOFILE soft limit: {soft} → {target}")


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


def _silence_disconnects(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """
    Drop CancelledError from unretrieved shielded futures.

    asgiref's ``SyncToAsync`` adapter shields the executor coroutine
    running a sync Django view. On client disconnect the outer task is
    cancelled; the inner future continues (sync work in a thread can't
    be cancelled), completes, and is then unretrieved — and asyncio's
    default handler logs that as "CancelledError exception in shielded
    future". The work itself isn't lost; there's just no client to hand
    the response to. Silencing keeps user-facing logs uncluttered.
    """
    if isinstance(context.get("exception"), asyncio.CancelledError):
        return
    loop.default_exception_handler(context)


async def _serve(server: Server) -> None:
    """Run granian until SHUTDOWN_EVENT fires, then stop gracefully."""
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_silence_disconnects)
    # ``PYTHONDEVMODE=1`` (set by bin/dev-server.sh when DEBUG=1) flips
    # asyncio into debug mode, which logs WARNINGs whenever a callback
    # exceeds ``slow_callback_duration`` (default 100ms). Codex routes
    # most requests through asgiref's ``AsyncToSync`` adapter — a sync
    # Django view on a thread pool, awaited from the loop — and a DB-
    # heavy view crossing 100ms is routine, not anomalous. Keep the
    # warning useful (a >5s callback is a real bug worth surfacing)
    # without spamming on every normal request.
    loop.slow_callback_duration = 5.0
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
    _raise_fd_limit()
    loguru_init()
    if codex_startup():
        run()
    codex_shutdown()


if __name__ == "__main__":
    main()
