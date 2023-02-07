"""Start and stop daemons."""
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.db.models.functions import Now

from codex.librarian.librariand import LibrarianDaemon
from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.logger.log_queue import LOG_QUEUE
from codex.logger.loggerd import Logger
from codex.models import AdminFlag, LibrarianStatus, Library, Timestamp
from codex.settings.logging import get_logger
from codex.settings.patch import patch_registration_setting
from codex.settings.settings import RESET_ADMIN


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
        LOG.info(f"Deleted {count} orphan {model._meta.verbose_name_plural}.")


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


class LifespanApplication:
    """Lifespan AGSI App."""

    SCOPE_TYPE = "lifespan"

    def __init__(self):
        """Create logger and librarian."""
        self.logger = Logger(LOG_QUEUE)
        self.librarian = LibrarianDaemon(LIBRARIAN_QUEUE, LOG_QUEUE)

    def codex_startup(self):
        """Initialize the database and start the daemons."""
        ensure_superuser()
        init_admin_flags()
        patch_registration_setting()
        init_timestamps()
        init_librarian_statuses()
        clear_library_status()
        cache.clear()
        self.librarian.start()
        LOG.info("Codex started up.")

    def codex_shutdown(self):
        """Stop the daemons."""
        LOG.info("Codex suprocesses shutting down...")
        self.librarian.join(5)
        self.librarian.close()
        LOG.info("Codex subprocesses shut down.")

    async def __call__(self, scope, receive, send):
        """Lifespan application."""
        print("__call__", scope)
        if scope["type"] != self.SCOPE_TYPE:
            return
        self.logger.start()
        LOG.debug("Lifespan application started.")
        while True:
            try:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    try:
                        await sync_to_async(self.codex_startup)()
                        await send({"type": "lifespan.startup.complete"})
                        LOG.debug("Lifespan startup complete.")
                    except Exception as exc:
                        await send({"type": "lifespan.startup.failed"})
                        LOG.error("Lifespan startup failed.")
                        raise exc
                elif message["type"] == "lifespan.shutdown":
                    LOG.debug("Lifespan shutdown started.")
                    try:
                        # block on the join
                        await sync_to_async(self.codex_shutdown)()
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
        self.logger.stop()
