#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""
import os

from asyncio import get_event_loop
from logging import getLogger

import django

from django.core.management import call_command
from hypercorn.asyncio import serve

from codex.asgi import application
from codex.settings.settings import DEBUG
from codex.settings.settings import HYPERCORN_CONFIG
from codex.signals import RESTART_EVENT
from codex.signals import SHUTDOWN_EVENT
from codex.signals import bind_signals


LOG = getLogger(__name__)


def set_env():
    """Set environment variables."""
    if DEBUG:
        os.environ["PYTHONDONTWRITEBYTECODE"] = "YES"
        LOG.setLevel("DEBUG")


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
    update_db()
    run()


if __name__ == "__main__":
    main()
