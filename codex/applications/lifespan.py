"""Start and stop daemons."""
import asyncio

from multiprocessing import Queue

from aioprocessing import AioQueue
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.db.models.functions import Now

from codex.channel_layer import CodexChannelLayer
from codex.librarian.librariand import LibrarianDaemon
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.notifierd import NotifierThread
from codex.logger.loggerd import Logger
from codex.logger.mp_queue import LOG_QUEUE
from codex.logger_base import LoggerBaseMixin
from codex.models import AdminFlag, LibrarianStatus, Library, Timestamp
from codex.settings.patch import patch_registration_setting
from codex.settings.settings import RESET_ADMIN


class LifespanApplication(LoggerBaseMixin):
    """Lifespan AGSI App."""

    SCOPE_TYPE = "lifespan"

    def __init__(self):
        """Create logger and librarian."""
        self.init_logger(LOG_QUEUE)
        self.loggerd = Logger(self.log_queue)
        self.notifier_queue = Queue()
        self.librarian = LibrarianDaemon(
            LIBRARIAN_QUEUE, self.log_queue, self.notifier_queue
        )

    async def init_notifier(self):
        broadcast_queue = AioQueue()
        channel_layer = get_channel_layer()
        channel_layer.channels[
            CodexChannelLayer.BROADCAST_CHANNEL_NAME
        ] = broadcast_queue
        self.notifier = NotifierThread(
            broadcast_queue,
            queue=self.notifier_queue,
            librarian_queue=LIBRARIAN_QUEUE,
            log_queue=LOG_QUEUE,
        )
        self.notifier.start()

    def ensure_superuser(self):
        """Ensure there is a valid superuser."""
        if RESET_ADMIN or not User.objects.filter(is_superuser=True).exists():
            admin_user, created = User.objects.update_or_create(
                username="admin",
                defaults={"is_staff": True, "is_superuser": True},
            )
            admin_user.set_password("admin")
            admin_user.save()
            prefix = "Cre" if created else "Upd"
            self.log.info(f"{prefix}ated admin user.")

    def _delete_orphans(self, model, field, names):
        """Delete orphans for declared models."""
        params = {f"{field}__in": names}
        query = model.objects.filter(~Q(**params))
        count = query.count()
        if count:
            query.delete()
            self.log.info(f"Deleted {count} orphan {model._meta.verbose_name_plural}.")

    def init_admin_flags(self):
        """Init admin flag rows."""
        self._delete_orphans(AdminFlag, "name", AdminFlag.FLAG_NAMES.keys())

        for name, on in AdminFlag.FLAG_NAMES.items():
            defaults = {"on": on}
            flag, created = AdminFlag.objects.get_or_create(
                defaults=defaults, name=name
            )
            if created:
                self.log.info(f"Created AdminFlag: {flag.name} = {flag.on}")

    def init_timestamps(self):
        """Init timestamps."""
        self._delete_orphans(Timestamp, "name", Timestamp.NAMES)

        for name in Timestamp.NAMES:
            _, created = Timestamp.objects.get_or_create(name=name)
            if created:
                self.log.info(f"Created {name} timestamp.")

    def init_librarian_statuses(self):
        """Init librarian statuses."""
        self._delete_orphans(LibrarianStatus, "type", LibrarianStatus.TYPES)

        defaults = {**LibrarianStatus.DEFAULT_PARAMS, "updated_at": Now()}
        for type in LibrarianStatus.TYPES:
            _, created = LibrarianStatus.objects.update_or_create(
                type=type, defaults=defaults
            )
            if created:
                self.log.info(f"Created {type} LibrarianStatus.")

    def clear_library_status(self):
        """Unset the update_in_progress flag for all libraries."""
        count = Library.objects.filter(update_in_progress=True).update(
            update_in_progress=False, updated_at=Now()
        )
        self.log.debug(f"Reset {count} Library's update_in_progress flag")

    def codex_startup(self):
        """Initialize the database and start the daemons."""
        self.ensure_superuser()
        self.init_admin_flags()
        patch_registration_setting()
        self.init_timestamps()
        self.init_librarian_statuses()
        self.clear_library_status()
        cache.clear()
        self.librarian.start()

    def codex_shutdown(self):
        """Stop the daemons."""
        self.librarian.shutdown()
        self.notifier.join()

    async def __call__(self, scope, receive, send):
        """Lifespan application."""
        if scope["type"] != self.SCOPE_TYPE:
            return
        self.loggerd.start()
        self.log.debug("Lifespan application started.")
        while True:
            try:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    try:
                        await sync_to_async(self.codex_startup)()
                        await self.init_notifier()
                        await send({"type": "lifespan.startup.complete"})
                        self.log.debug("Lifespan startup complete.")
                    except Exception as exc:
                        await send({"type": "lifespan.startup.failed"})
                        self.log.error("Lifespan startup failed.")
                        raise exc
                elif message["type"] == "lifespan.shutdown":
                    self.log.debug("Lifespan shutdown started.")
                    try:
                        await sync_to_async(self.codex_shutdown)()
                        await send({"type": "lifespan.shutdown.complete"})
                        self.log.debug("Lifespan shutdown complete.")
                    except Exception as exc:
                        await send({"type": "lifespan.shutdown.failed"})
                        self.log.error("Lifespan shutdown failed.")
                        raise exc
                    break
            except Exception as exc:
                self.log.exception(exc)
        self.log.debug("Lifespan application stopped.")
        self.loggerd.stop()
