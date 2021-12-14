"""Start and stop daemons."""
import os
import platform

from logging import getLogger
from multiprocessing import set_start_method

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.db.models.functions import Now

from codex.librarian.librariand import LibrarianDaemon
from codex.models import AdminFlag, Library
from codex.websocket_server import Notifier


RESET_ADMIN = bool(os.environ.get("CODEX_RESET_ADMIN"))
LOG = getLogger(__name__)


def ensure_superuser():
    """Ensure there is a valid superuser."""
    if RESET_ADMIN or not User.objects.filter(is_superuser=True).exists():
        admin_user, created = User.objects.update_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True},
        )
        admin_user.set_password("admin")  # type: ignore
        admin_user.save()
        prefix = "Cre" if created else "Upd"
        LOG.info(f"{prefix}ated admin user.")


def init_admin_flags():
    """Init admin flag rows."""
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
    query = AdminFlag.objects.filter(~Q(name__in=AdminFlag.FLAG_NAMES))
    count = query.count()
    if count:
        query.delete()
        LOG.info(f"Deleted {count} orphan AdminFlags.")


def unset_update_in_progress():
    """Unset the update_in_progress flag for all libraries."""
    count = Library.objects.filter(update_in_progress=True).update(
        update_in_progress=False, updated_at=Now()
    )
    LOG.debug(f"Reset {count} Library's update_in_progress flag")


def codex_startup():
    """Initialize the database and start the daemons."""
    ensure_superuser()
    init_admin_flags()
    unset_update_in_progress()
    cache.clear()

    if platform.system() == "Darwin":
        # Fixes LIBRARIAN_QUEUE sharing with default spawn start method. The spawn
        # method is also very very slow. Use fork and the
        # OBJC_DISABLE_INITIALIZE_FORK_SAFETY environment variable for macOS.
        # XXX https://bugs.python.org/issue40106
        #
        # This must happen before we create the Librarian process
        set_start_method("fork", force=True)

    Notifier.startup()
    LibrarianDaemon.startup()


def codex_shutdown():
    """Stop the daemons."""
    LOG.info("Shutting down Codex...")
    LibrarianDaemon.shutdown()
    Notifier.shutdown()


async def lifespan_application(_scope, receive, send):
    """Lifespan application."""
    LOG.debug("Lifespan application started.")
    while True:
        try:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    await sync_to_async(codex_startup)()
                    await send({"type": "lifespan.startup.complete"})
                    LOG.debug("Lifespan startup complete.")
                except Exception as exc:
                    await send({"type": "lifespan.startup.failed"})
                    LOG.error("Lfespan startup failed.")
                    raise exc
            elif message["type"] == "lifespan.shutdown":
                LOG.debug("Lifespan shutdown started.")
                try:
                    # block on the join
                    codex_shutdown()
                    await send({"type": "lifespan.shutdown.complete"})
                    LOG.debug("Lifespan shutdown complete.")
                except Exception as exc:
                    await send({"type": "lifespan.startup.failed"})
                    LOG.error("Lifespan shutdown failed.")
                    raise exc
                break
        except Exception as exc:
            LOG.exception(exc)
    LOG.debug("Lifespan application stopped.")
