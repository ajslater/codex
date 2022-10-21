"""Start and stop daemons."""
import multiprocessing
import os
import time

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.db.models.functions import Now

from codex.darwin_mp import force_darwin_multiprocessing_fork
from codex.librarian.librariand import LibrarianDaemon
from codex.logger.loggerd import Logger
from codex.models import AdminFlag, LibrarianStatus, Library, Timestamp
from codex.notifier.notifierd import Notifier
from codex.settings.logging import get_logger
from codex.settings.patch import patch_registration_setting


RESET_ADMIN = bool(os.environ.get("CODEX_RESET_ADMIN"))
LOG = get_logger(__name__)


def ensure_superuser():
    """Ensure there is a valid superuser."""
    if RESET_ADMIN or not User.objects.filter(is_superuser=True).exists():
        admin_user, created = User.objects.update_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True},
        )
        admin_user.set_password("admin")
        admin_user.save()
        prefix = "Cre" if created else "Upd"
        LOG.info(f"{prefix}ated admin user.")


def _delete_orphans(model, field, names):
    """Delete orphans for declared models."""
    params = {f"{field}__in": names}
    query = model.objects.filter(~Q(**params))
    count = query.count()
    if count:
        query.delete()
        LOG.info(f"Deleted {count} orphan {model.verbose_name_plural}.")


def init_admin_flags():
    """Init admin flag rows."""
    _delete_orphans(AdminFlag, "name", AdminFlag.FLAG_NAMES.keys())

    for name, on in AdminFlag.FLAG_NAMES.items():
        defaults = {"on": on}
        flag, created = AdminFlag.objects.get_or_create(defaults=defaults, name=name)
        if created:
            LOG.info(f"Created AdminFlag: {flag.name} = {flag.on}")


def init_timestamps():
    """Init timestamps."""
    _delete_orphans(Timestamp, "name", Timestamp.NAMES)

    for name in Timestamp.NAMES:
        _, created = Timestamp.objects.get_or_create(name=name)
        if created:
            LOG.info(f"Created {name} timestamp.")


def init_librarian_statuses():
    """Init librarian statuses."""
    _delete_orphans(LibrarianStatus, "type", LibrarianStatus.TYPES)

    defaults = {**LibrarianStatus.DEFAULT_PARAMS, "updated_at": Now()}
    for type in LibrarianStatus.TYPES:
        _, created = LibrarianStatus.objects.update_or_create(
            type=type, defaults=defaults
        )
        if created:
            LOG.info(f"Created {type} LibrarianStatus.")


def clear_library_status():
    """Unset the update_in_progress flag for all libraries."""
    count = Library.objects.filter(update_in_progress=True).update(
        update_in_progress=False, updated_at=Now()
    )
    LOG.debug(f"Reset {count} Library's update_in_progress flag")


def codex_startup():
    """Initialize the database and start the daemons."""
    ensure_superuser()
    init_admin_flags()
    patch_registration_setting()
    init_timestamps()
    init_librarian_statuses()
    clear_library_status()
    cache.clear()
    force_darwin_multiprocessing_fork()

    Notifier.startup()
    LibrarianDaemon.startup()


def codex_shutdown():
    """Stop the daemons."""
    LOG.info("Codex suprocesses shutting down...")
    LibrarianDaemon.shutdown()
    Notifier.shutdown()
    if multiprocessing.active_children():
        LOG.verbose("Codex suprocesses not joined...")
        time.sleep(2)
        for child in multiprocessing.active_children():
            child.terminate()
            LOG.verbose(f"Killed subprocess {child}")
    LOG.info("Codex subprocesses shut down.")


async def lifespan_application(_scope, receive, send):
    """Lifespan application."""
    Logger.startup()
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
    Logger.shutdown()
