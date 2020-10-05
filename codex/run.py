#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""
import asyncio
import os
import shutil
import signal

from logging import getLogger

import django

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from hypercorn.asyncio import serve
from hypercorn.config import Config

from codex.asgi import application
from codex.librarian.librariand import PORT
from codex.models import AdminFlag
from codex.models import Library
from codex.settings import CODEX_PATH
from codex.settings import CONFIG_PATH
from codex.settings import CONFIG_STATIC
from codex.settings import DEBUG


CONFIG_TOML = CONFIG_PATH / "hypercorn.toml"
CONFIG_DEFAULT_TOML = CODEX_PATH / "hypercorn.toml.default"

LOG = getLogger(__name__)
RESET_ADMIN = bool(os.environ.get("CODEX_RESET_ADMIN"))
SIGNAL_NAMES = {"SIGINT", "SIGTERM", "SIGBREAK"}
RESTART_EVENT = asyncio.Event()
SHUTDOWN_EVENT = asyncio.Event()


def ensure_config():
    """Ensure that a valid config exists."""
    # make the config dir and the static dir.
    CONFIG_STATIC.mkdir(parents=True, exist_ok=True)
    if not CONFIG_TOML.exists():
        shutil.copy(CONFIG_DEFAULT_TOML, CONFIG_TOML)
        LOG.info(f"Copied default config to {CONFIG_TOML}")


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


def get_hypercorn_config():
    """Configure the hypercorn server."""
    config = Config.from_toml(CONFIG_TOML)
    LOG.info(f"Loaded config from {CONFIG_TOML}")
    if DEBUG:
        config.use_reloader = True
        LOG.info("Reload hypercorn if files change")

    # Don't nuke existing loggers
    config.logconfig_dict = {"disable_existing_loggers": False}
    # Store port number in shared memory for librariand websocket server
    PORT.value = int(config.bind[0].split(":")[1])
    return config


def bind_signals(loop):
    """Binds signals to the handlers."""
    for signal_name in SIGNAL_NAMES:
        sig = getattr(signal, signal_name, None)
        if sig:
            loop.add_signal_handler(sig, _shutdown_signal_handler)
    loop.add_signal_handler(signal.SIGUSR1, _restart_signal_handler)


def run():
    """Run Codex."""
    config = get_hypercorn_config()

    # configure the loop
    loop = asyncio.get_event_loop()
    bind_signals(loop)
    # run it and block
    loop.run_until_complete(
        serve(application, config, shutdown_trigger=SHUTDOWN_EVENT.wait)
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
    ensure_config()
    setup_db()
    cache.clear()
    run()


if __name__ == "__main__":
    main()
