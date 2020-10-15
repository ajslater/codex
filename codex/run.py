#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""
import asyncio
import os
import signal

from logging import getLogger

import django

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from hypercorn.asyncio import serve

from codex.asgi import application
from codex.models import AdminFlag
from codex.models import Library
from codex.settings.settings import DEBUG
from codex.settings.settings import HYPERCORN_CONFIG


LOG = getLogger(__name__)
RESET_ADMIN = bool(os.environ.get("CODEX_RESET_ADMIN"))
SIGNAL_NAMES = {"SIGINT", "SIGTERM", "SIGBREAK"}
RESTART_EVENT = asyncio.Event()
SHUTDOWN_EVENT = asyncio.Event()


def update_db():
    """Update the db to latest migrations."""
    call_command("makemigrations", "codex")
    call_command("migrate")


def ensure_superuser():
    """Ensure there is a valid superuser."""
    User = get_user_model()  # noqa N806

    if RESET_ADMIN or not User.objects.filter(is_superuser=True).exists():
        admin_user, created = User.objects.update_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True},
        )
        admin_user.set_password("admin")
        admin_user.save()
        prefix = "Cre" if created else "Upd"
        LOG.info(f"{prefix}ated admin user.")


def init_admin_flags():
    """Init admin flag rows."""
    # AdminFlag = apps.get_model("codex", "AdminFlag")  # noqa N806
    for name in AdminFlag.FLAG_NAMES:
        if name in AdminFlag.DEFAULT_FALSE:
            defaults = {"on": False}
            flag, created = AdminFlag.objects.get_or_create(
                defaults=defaults, name=name
            )
        else:
            flag, created = AdminFlag.objects.get_or_create(name=name)
        if created:
            LOG.info(f"Created AdminFlag: {flag.name} = {flag.on}")


def unset_scan_in_progress():
    """Unset the scan_in_progres flag for all libraries."""
    stuck_libraries = Library.objects.filter(scan_in_progress=True).only(
        "scan_in_progress", "path"
    )
    for library in stuck_libraries:
        library.scan_in_progress = False
        LOG.info(f"Removing scan lock from {library.path}")
    Library.objects.bulk_update(stuck_libraries, ["scan_in_progress"])


def _shutdown_signal_handler():
    global SHUTDOWN_EVENT
    if SHUTDOWN_EVENT.is_set():
        return
    LOG.info("Asking hypercorn to shut down gracefully. Could take 5 seconds...")
    SHUTDOWN_EVENT.set()


def _restart_signal_handler():
    global RESTART_EVENT
    if RESTART_EVENT.is_set():
        return
    LOG.info("Restart signal received.")
    RESTART_EVENT.set()
    _shutdown_signal_handler()


def setup_db():
    """Set up database before run."""
    django.setup()
    update_db()
    ensure_superuser()
    init_admin_flags()
    unset_scan_in_progress()


def bind_signals(loop):
    """Binds signals to the handlers."""
    for signal_name in SIGNAL_NAMES:
        sig = getattr(signal, signal_name, None)
        if sig:
            loop.add_signal_handler(sig, _shutdown_signal_handler)
    loop.add_signal_handler(signal.SIGUSR1, _restart_signal_handler)


def run():
    """Run Codex."""
    # configure the loop
    loop = asyncio.get_event_loop()
    bind_signals(loop)
    # run it and block
    loop.run_until_complete(
        serve(application, HYPERCORN_CONFIG, shutdown_trigger=SHUTDOWN_EVENT.wait)
    )
    if RESTART_EVENT.is_set():
        import sys

        LOG.info("Restarting. Hold on to your butts.")
        os.execv(__file__, sys.argv)
    LOG.info("Goodbye.")


def set_env():
    """Set environment variables."""
    # This papers over a macos crash that can happen with
    # multirocessing start_method: fork
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
    if DEBUG:
        os.environ["PYTHONDONTWRITEBYTECODE"] = "YES"
        LOG.setLevel("DEBUG")


def main():
    """Set up and run Codex."""
    set_env()
    setup_db()
    cache.clear()
    run()


if __name__ == "__main__":
    main()
