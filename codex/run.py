#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""
import os
import re
import sqlite3

from asyncio import get_event_loop
from logging import getLogger

import django

from django.core.management import call_command
from hypercorn.asyncio import serve

from codex.asgi import application
from codex.settings.settings import CONFIG_PATH, DB_PATH, DEBUG, HYPERCORN_CONFIG
from codex.signals import RESTART_EVENT, SHUTDOWN_EVENT, bind_signals


REPAIR_FLAG_PATH = CONFIG_PATH / "rebuild_db"
DUMP_LINE_MATCHER = re.compile("TRANSACTION|ROLLBACK|COMMIT")
REBUILT_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".rebuilt")
BACKUP_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".backup")
LOG = getLogger(__name__)


def set_env():
    """Set environment variables."""
    if DEBUG:
        os.environ["PYTHONDONTWRITEBYTECODE"] = "YES"
        LOG.setLevel("DEBUG")


def rebuild_db():
    """Dump and rebuild the database."""
    # Drastic
    if not REPAIR_FLAG_PATH.exists():
        return

    LOG.warning("REBUILDING DATABASE!!")
    with sqlite3.connect(REBUILT_DB_PATH) as new_db_conn:
        new_db_cur = new_db_conn.cursor()
        with sqlite3.connect(DB_PATH) as old_db_conn:
            for line in old_db_conn.iterdump():
                if DUMP_LINE_MATCHER.search(line):
                    continue
                new_db_cur.execute(line)

    DB_PATH.rename(BACKUP_DB_PATH)
    LOG.info("Backed up old db to %s", BACKUP_DB_PATH)
    REBUILT_DB_PATH.replace(DB_PATH)
    REPAIR_FLAG_PATH.unlink(missing_ok=True)
    LOG.info("Rebuilt database.")


def update_db():
    """Update the db to latest migrations."""
    django.setup()
    call_command("makemigrations", "codex")
    call_command("migrate")


def restart():
    """Restart this process."""
    import sys

    LOG.info("Restarting. Hold on to your butts.")
    os.execv(__file__, sys.argv)


def run():
    """Run Codex."""
    # configure the loop
    loop = get_event_loop()
    bind_signals(loop)
    loop.run_until_complete(
        serve(application, HYPERCORN_CONFIG, shutdown_trigger=SHUTDOWN_EVENT.wait)
    )
    loop._run_once()
    if RESTART_EVENT.is_set():
        restart()
    LOG.info("Goodbye.")


def main():
    """Set up and run Codex."""
    set_env()
    rebuild_db()
    update_db()
    run()


if __name__ == "__main__":
    main()
