#!/usr/bin/env python
import asyncio
import os
import shutil

from logging import getLogger

import django

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from hypercorn.asyncio import serve
from hypercorn.config import Config

from codex.asgi import application
from codex.librarian.librariand import PORT
from codex.models import Library
from codex.settings import CODEX_PATH
from codex.settings import CONFIG_PATH
from codex.settings import CONFIG_STATIC


CONFIG_TOML = CONFIG_PATH / "hypercorn.toml"
CONFIG_DEFAULT_TOML = CODEX_PATH / "hypercorn.toml.default"

LOG = getLogger(__name__)
DEV = bool(os.environ.get("DEV"))
RESET_ADMIN = bool(os.environ.get("CODEX_RESET_ADMIN"))


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


def unset_scan_in_progress():
    stuck_libraries = Library.objects.filter(scan_in_progress=True).only(
        "scan_in_progress", "path"
    )
    for library in stuck_libraries:
        library.scan_in_progress = False
        LOG.info(f"Removing scan lock from {library.path}")
    Library.objects.bulk_update(stuck_libraries, ["scan_in_progress"])


def setup_db():
    """Setup the database before we run."""
    django.setup()
    update_db()
    ensure_superuser()
    unset_scan_in_progress()


def run():
    config = Config.from_toml(CONFIG_TOML)
    LOG.info(f"Loaded config from {CONFIG_TOML}")
    if DEV:
        config.use_reloader = True
        LOG.info("Reload hypercorn if files change")
    # Store port number in shared memory for librariand websocket
    PORT.value = int(config.bind[0].split(":")[1])

    # This papers over a macos crash that i think only happens on
    #   development server rapid restarts
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
    asyncio.run(serve(application, config))


def main():
    if DEV:
        LOG.setLevel("DEBUG")
    ensure_config()
    setup_db()
    cache.clear()
    run()


if __name__ == "__main__":
    main()
