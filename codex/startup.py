"""Initialize Codex Dataabse before running."""
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.db.models import Q
from django.db.models.functions import Now

from codex.integrity import has_unapplied_migrations, rebuild_db, repair_db
from codex.librarian.janitor.janitor import Janitor
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.logging import get_logger
from codex.logger.mp_queue import LOG_QUEUE
from codex.models import AdminFlag, LibrarianStatus, Library, Timestamp
from codex.registration import patch_registration_setting
from codex.settings.settings import (
    BACKUP_DB_PATH,
    HYPERCORN_CONFIG,
    HYPERCORN_CONFIG_TOML,
    MAX_DB_OPS,
    RESET_ADMIN,
)
from codex.version import VERSION

LOG = get_logger(__name__)


def backup_db_before_migration():
    """If there are migrations to do, backup the db."""
    suffix = f".before-v{VERSION}{BACKUP_DB_PATH.suffix}"
    backup_path = BACKUP_DB_PATH.with_suffix(suffix)
    janitor = Janitor(LOG_QUEUE, LIBRARIAN_QUEUE)
    janitor.backup_db(backup_path)


def ensure_db_schema():
    """Ensure the db is good and up to date."""
    LOG.debug("Ensuring db is good and up to date...")
    table_names = connection.introspection.table_names()
    db_exists = "django_migrations" in table_names
    if db_exists:
        rebuild_db()
        repair_db()
    if not db_exists or has_unapplied_migrations():
        if db_exists:
            backup_db_before_migration()
        call_command("migrate")
    else:
        LOG.info("Database up to date.")
    LOG.info("Database ready.")


def ensure_superuser():
    """Ensure there is a valid superuser."""
    from django.contrib.auth.models import User

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
        ts, created = Timestamp.objects.get_or_create(name=name)
        if name == Timestamp.API_KEY and not ts.version:
            ts.save_uuid_version()
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


def ensure_db_rows():
    """Ensure database content is good."""
    ensure_superuser()
    init_admin_flags()
    init_timestamps()
    init_librarian_statuses()
    clear_library_status()


def codex_init():
    """Initialize the database and start the daemons."""
    ensure_db_schema()
    ensure_db_rows()
    patch_registration_setting()
    cache.clear()
    LOG.debug(f"max_db_ops: {MAX_DB_OPS}")
    LOG.info(f"root_path: {HYPERCORN_CONFIG.root_path}")
    if HYPERCORN_CONFIG.use_reloader:
        LOG.info(f"Will reload hypercorn if {HYPERCORN_CONFIG_TOML} changes")
