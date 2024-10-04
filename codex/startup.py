"""Initialize Codex Dataabse before running."""

from pathlib import Path

from django.core.cache import cache
from django.db.models import F, Q
from django.db.models.functions import Now

from codex.choices import ADMIN_FLAG_CHOICES, ADMIN_STATUS_TITLES
from codex.db import ensure_db_schema
from codex.logger.logging import get_logger
from codex.models import AdminFlag, CustomCover, LibrarianStatus, Library, Timestamp
from codex.registration import patch_registration_setting
from codex.settings.settings import (
    CUSTOM_COVERS_DIR,
    CUSTOM_COVERS_SUBDIR,
    HYPERCORN_CONFIG,
    HYPERCORN_CONFIG_TOML,
    RESET_ADMIN,
)
from codex.status_controller import STATUS_DEFAULTS

LOG = get_logger(__name__)


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
    _delete_orphans(AdminFlag, "key", AdminFlag.FlagChoices.values)

    for key in AdminFlag.FlagChoices.values:
        defaults = {"key": key, "on": key not in AdminFlag.FALSE_DEFAULTS}
        flag, created = AdminFlag.objects.get_or_create(defaults=defaults, key=key)
        if created:
            title = ADMIN_FLAG_CHOICES[flag.key]
            LOG.info(f"Created AdminFlag: {title} = {flag.on}")


def init_timestamps():
    """Init timestamps."""
    _delete_orphans(Timestamp, "key", Timestamp.TimestampChoices.values)

    for key in Timestamp.TimestampChoices.values:
        ts, created = Timestamp.objects.get_or_create(key=key)
        if key == Timestamp.TimestampChoices.API_KEY.value and not ts.version:
            ts.save_uuid_version()
        if created:
            label = Timestamp.TimestampChoices(ts.key).label
            LOG.debug(f"Created {label} timestamp.")


def init_librarian_statuses():
    """Init librarian statuses."""
    status_types = [choice[0] for choice in LibrarianStatus.CHOICES]
    _delete_orphans(LibrarianStatus, "status_type", status_types)

    for status_type in status_types:
        _, created = LibrarianStatus.objects.update_or_create(
            defaults=STATUS_DEFAULTS, status_type=status_type
        )
        if created:
            title = ADMIN_STATUS_TITLES[status_type]
            LOG.debug(f"Created {title} LibrarianStatus.")


def clear_library_status():
    """Unset the update_in_progress flag for all libraries."""
    count = Library.objects.filter(update_in_progress=True).update(
        update_in_progress=False, updated_at=Now()
    )
    if count:
        LOG.debug(f"Reset {count} Libraries' update_in_progress flag")


def init_custom_cover_dir():
    """Initialize the Custom Cover Dir singleton row."""
    defaults = dict(**Library.CUSTOM_COVERS_DIR_DEFAULTS, path=CUSTOM_COVERS_DIR)
    covers_library, created = Library.objects.get_or_create(
        defaults=defaults, covers_only=True
    )
    if created:
        LOG.info("Created Custom Covers Dir settings in the db.")

    old_path = covers_library.path
    if Path(old_path) != CUSTOM_COVERS_DIR:
        Library.objects.filter(covers_only=True).update(path=str(CUSTOM_COVERS_DIR))
        LOG.info(
            f"Updated Custom Group Covers Dir path from {old_path} to {CUSTOM_COVERS_DIR}."
        )


def update_custom_covers_for_config_dir():
    """Update custom covers if the config dir changes."""
    # This is okay, but I wouldn't need to do it if paths were constructed from
    # parent_folder and library.path
    # Fast lookup without relations seems better though, paths shouldn't change too much.

    # Determine which covers need re-pathing
    update_covers = []
    delete_cover_pks = []
    update_fields = ("path", "updated_at")
    group_covers = (
        CustomCover.objects.filter(library__covers_only=True)
        .exclude(path__startswith=F("library__path"))
        .only(*update_fields)
    )
    LOG.debug(f"Checking that group custom covers are under {CUSTOM_COVERS_DIR}")
    for cover in group_covers.iterator():
        old_path = cover.path
        parts = old_path.rsplit(f"/{CUSTOM_COVERS_SUBDIR}/")
        if len(parts) < 2:  # noqa: PLR2004
            delete_cover_pks.append(cover.pk)
            continue
        new_path = CUSTOM_COVERS_DIR / parts[1]
        if new_path.exists():
            cover.path = str(new_path)
            update_covers.append(cover)
        else:
            delete_cover_pks.append(cover.pk)
    update_count = len(update_covers)
    LOG.debug(
        f"Found {update_count} custom covers to update, {len(delete_cover_pks)} to delete."
    )

    # Update covers
    if update_count:
        CustomCover.objects.bulk_update(update_covers, update_fields)
        LOG.info(
            f"Updated {update_count} CustomCovers sources to point to new config dir"
        )

    # Delete covers we can't reliably update.
    if delete_cover_pks:
        delete_qs = CustomCover.objects.filter(pk__in=delete_cover_pks)
        delete_count = delete_qs.count()
        delete_qs.delete()
        LOG.warning(
            f"Delete {delete_count} CustomCovers that could not be re-sourced after config dir change."
        )


def ensure_db_rows():
    """Ensure database content is good."""
    ensure_superuser()
    init_admin_flags()
    init_timestamps()
    init_librarian_statuses()
    clear_library_status()
    init_custom_cover_dir()
    update_custom_covers_for_config_dir()


def codex_init():
    """Initialize the database and start the daemons."""
    if not ensure_db_schema():
        return False
    ensure_db_rows()
    patch_registration_setting()
    cache.clear()
    LOG.info(f"root_path: {HYPERCORN_CONFIG.root_path}")
    if HYPERCORN_CONFIG.use_reloader:
        LOG.info(f"Will reload hypercorn if {HYPERCORN_CONFIG_TOML} changes")
    return True
