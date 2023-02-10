#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""
from asyncio import new_event_loop
from multiprocessing import set_start_method
from os import execv

from django.core.management import call_command
from hypercorn.asyncio import serve

from codex.asgi import application
from codex.integrity import has_unapplied_migrations, rebuild_db, repair_db
from codex.librarian.janitor.janitor import Janitor
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.logger.mp_queue import LOG_QUEUE
from codex.settings.settings import BACKUP_DB_PATH, HYPERCORN_CONFIG
from codex.signals.os_signals import RESTART_EVENT, SHUTDOWN_EVENT, bind_signals
from codex.version import VERSION


LOG = get_logger(__name__)


def backup_db_before_migration():
    """If there are migrations to do, backup the db."""
    if not has_unapplied_migrations():
        return
    suffix = f".before-v{VERSION}{BACKUP_DB_PATH.suffix}"
    backup_path = BACKUP_DB_PATH.with_suffix(suffix)
    janitor = Janitor(LOG_QUEUE, LIBRARIAN_QUEUE)
    janitor.backup_db(backup_path)


def restart():
    """Restart this process."""
    import sys

    LOG.info("Restarting Codex. Hold on to your butts...")
    execv(__file__, sys.argv)  # nosec


def run():
    """Run Codex."""
    LOG.info(f"root_path: {HYPERCORN_CONFIG.root_path}")
    # TODO try to replace with wrapping serve in a bind, then serve coroutine.
    loop = new_event_loop()
    bind_signals(loop)
    loop.run_until_complete(
        serve(
            application,
            HYPERCORN_CONFIG,
            shutdown_trigger=SHUTDOWN_EVENT.wait,  # type: ignore
        )
    )
    if RESTART_EVENT.is_set():
        restart()
    LOG.info("Goodbye.")


def main():
    """Set up and run Codex."""
    LOG.info(f"Running Codex v{VERSION}")
    rebuild_db()
    repair_db()
    backup_db_before_migration()
    call_command("migrate")
    run()


if __name__ == "__main__":
    set_start_method("spawn", force=True)
    main()
