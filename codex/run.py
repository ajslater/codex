#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""
import os

from asyncio import new_event_loop

from django.core.management import call_command
from hypercorn.asyncio import serve

from codex.asgi import application
from codex.integrity import has_unapplied_migrations, rebuild_db, repair_db
from codex.librarian.janitor.vacuum import backup_db
from codex.settings.logging import get_logger
from codex.settings.settings import BACKUP_DB_PATH, DEBUG, HYPERCORN_CONFIG
from codex.signals import RESTART_EVENT, SHUTDOWN_EVENT, bind_signals
from codex.version import VERSION


LOG = get_logger(__name__)


def set_env():
    """Set environment variables."""
    if DEBUG:
        os.environ["PYTHONDONTWRITEBYTECODE"] = "YES"
        LOG.setLevel("DEBUG")


def backup_db_before_migration():
    """If there are migrations to do, backup the db."""
    if not has_unapplied_migrations():
        return
    suffix = f".before-v{VERSION}{BACKUP_DB_PATH.suffix}"
    backup_path = BACKUP_DB_PATH.with_suffix(suffix)
    backup_db(backup_path)


def update_db():
    """Update the db to latest migrations."""
    if DEBUG:
        call_command("makemigrations", "codex")
    call_command("migrate")


def restart():
    """Restart this process."""
    import sys

    LOG.info("Restarting Codex. Hold on to your butts...")
    os.execv(__file__, sys.argv)  # nosec


def run():
    """Run Codex."""
    # configure the loop
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
    set_env()
    rebuild_db()
    repair_db()
    backup_db_before_migration()
    update_db()
    run()


if __name__ == "__main__":
    main()
