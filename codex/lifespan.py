"""Start and stop daemons."""
import os

from logging import getLogger

import django

from asgiref.sync import sync_to_async
from django.core.cache import cache


RESET_ADMIN = bool(os.environ.get("CODEX_RESET_ADMIN"))
LOG = getLogger(__name__)


def ensure_superuser():
    """Ensure there is a valid superuser."""
    from django.contrib.auth import get_user_model

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
    from codex.models import AdminFlag

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
    from codex.models import Library

    stuck_libraries = Library.objects.filter(scan_in_progress=True).only(
        "scan_in_progress", "path"
    )
    for library in stuck_libraries:
        library.scan_in_progress = False
        LOG.info(f"Removing scan lock from {library.path}")
    Library.objects.bulk_update(stuck_libraries, ["scan_in_progress"])


def codex_startup():
    """Start the daemons. But don't import them until django is set up."""
    django.setup()
    ensure_superuser()
    init_admin_flags()
    unset_scan_in_progress()
    cache.clear()

    from codex.librarian.librariand import LibrarianDaemon
    from codex.websocket_server import FloodControlThread

    LibrarianDaemon.startup()
    FloodControlThread.startup()


def codex_shutdown():
    """Stop the daemons. But don't import them until django is set up."""
    from codex.librarian.librariand import LibrarianDaemon
    from codex.websocket_server import FloodControlThread

    LibrarianDaemon.shutdown()
    FloodControlThread.shutdown()


async def lifespan_application(scope, receive, send):
    """Lifespan application."""
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            try:
                await sync_to_async(codex_startup)()
                await send({"type": "lifespan.startup.complete"})
                LOG.debug("Lifespan startup complete.")
            except Exception as exc:
                LOG.error(exc)
                await send({"type": "lifespan.startup.failed"})
        elif message["type"] == "lifespan.shutdown":
            LOG.debug("Lifespan shutdown started.")
            try:
                # block on the join
                codex_shutdown()
                await send({"type": "lifespan.shutdown.complete"})
                LOG.debug("Lifespan shutdown complete.")
            except Exception as exc:
                await send({"type": "lifespan.startup.failed"})
                LOG.error("Lfespan shutdown failed.")
                LOG.error(exc)
            break
