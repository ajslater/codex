#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""
import os

from asyncio import get_event_loop
from logging import getLogger

import django

from django.core.management import call_command
from hypercorn.asyncio import serve

from codex.asgi import application
from codex.integrity import rebuild_db, repair_db
from codex.settings.settings import DEBUG, HYPERCORN_CONFIG
from codex.signals import RESTART_EVENT, SHUTDOWN_EVENT, bind_signals


LOG = getLogger(__name__)


def set_env():
    """Set environment variables."""
    if DEBUG:
        os.environ["PYTHONDONTWRITEBYTECODE"] = "YES"
        # Overwritten when we import settings in django.setup()
        LOG.setLevel("DEBUG")


def update_db():
    """Update the db to latest migrations."""
    django.setup()
    call_command("makemigrations", "codex")
    call_command("migrate")


def restart():
    """Restart this process."""
    import sys

    LOG.info("Restarting Codex. Hold on to your butts...")
    os.execv(__file__, sys.argv)


def run():
    """Run Codex."""
    # configure the loop
    loop = get_event_loop()
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
    set_env()
    rebuild_db()
    repair_db()
    update_db()
    run()


if __name__ == "__main__":
    main()
