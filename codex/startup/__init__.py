"""Initialize Codex Dataabse before running."""

from pathlib import Path

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import F, Q
from django.db.models.functions import Now
from loguru import logger
from rest_framework.authtoken.models import Token

from codex.choices.admin import AdminFlagChoices
from codex.librarian.status_controller import STATUS_DEFAULTS
from codex.models import AdminFlag, CustomCover, LibrarianStatus, Library, Timestamp
from codex.settings import (
    AUTH_REMOTE_USER,
    CUSTOM_COVERS_DIR,
    CUSTOM_COVERS_SUBDIR,
    HYPERCORN_CONFIG,
    HYPERCORN_CONFIG_TOML,
    RESET_ADMIN,
)
from codex.startup.db import ensure_db_schema
from codex.startup.registration import patch_registration_setting


def ensure_superuser():
    """Ensure there is a valid superuser."""
    if RESET_ADMIN or not User.objects.filter(is_superuser=True).exists():
        admin_user, created = User.objects.update_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True, "is_active": True},
        )
        admin_user.set_password("admin")
        admin_user.save()
        prefix = "Cre" if created else "Upd"
        logger.success(f"{prefix}ated admin user.")


def _delete_orphans(model, field, names):
    """Delete orphans for declared models."""
    params = {f"{field}__in": names}
    query = model.objects.filter(~Q(**params))
    count, _ = query.delete()
    if count:
        logger.info(f"Deleted {count} orphan {model._meta.verbose_name_plural}.")


def init_admin_flags():
    """Init admin flag rows."""
    _delete_orphans(AdminFlag, "key", AdminFlagChoices.values)

    for key, title in AdminFlagChoices.choices:
        defaults = {"key": key, "on": key not in AdminFlag.FALSE_DEFAULTS}
        flag, created = AdminFlag.objects.get_or_create(defaults=defaults, key=key)
        if created:
            logger.info(f"Created AdminFlag: {title} = {flag.on}")


def init_timestamps():
    """Init timestamps."""
    _delete_orphans(Timestamp, "key", Timestamp.Choices.values)

    for enum in Timestamp.Choices:
        key = enum.value
        ts, created = Timestamp.objects.get_or_create(key=key)
        if enum == Timestamp.Choices.API_KEY and not ts.version:
            ts.save_uuid_version()
        if created:
            label = Timestamp.Choices(ts.key).label
            logger.debug(f"Created {label} timestamp.")


def init_librarian_statuses():
    """Init librarian statuses."""
    _delete_orphans(
        LibrarianStatus,
        "status_type",
        LibrarianStatus.StatusChoices.values,
    )

    for status_type, title in LibrarianStatus.StatusChoices.choices:
        _, created = LibrarianStatus.objects.update_or_create(
            defaults=STATUS_DEFAULTS, status_type=status_type
        )
        if created:
            logger.debug(f"Created {title} LibrarianStatus.")


def clear_library_status():
    """Unset the update_in_progress flag for all libraries."""
    count = Library.objects.filter(update_in_progress=True).update(
        update_in_progress=False, updated_at=Now()
    )
    if count:
        logger.debug(f"Reset {count} Libraries' update_in_progress flag")


def init_custom_cover_dir():
    """Initialize the Custom Cover Dir singleton row."""
    defaults = dict(**Library.CUSTOM_COVERS_DIR_DEFAULTS, path=CUSTOM_COVERS_DIR)
    covers_library, created = Library.objects.get_or_create(
        defaults=defaults, covers_only=True
    )
    if created:
        logger.info("Created Custom Covers Dir settings in the db.")

    old_path = covers_library.path
    if Path(old_path) != CUSTOM_COVERS_DIR:
        Library.objects.filter(covers_only=True).update(path=str(CUSTOM_COVERS_DIR))
        logger.info(
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
    logger.debug(f"Checking that group custom covers are under {CUSTOM_COVERS_DIR}")
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
    logger.debug(
        f"Found {update_count} custom covers to update, {len(delete_cover_pks)} to delete."
    )

    # Update covers
    if update_count:
        CustomCover.objects.bulk_update(update_covers, update_fields)
        logger.info(
            f"Updated {update_count} CustomCovers sources to point to new config dir"
        )

    # Delete covers we can't reliably update.
    if delete_cover_pks:
        delete_qs = CustomCover.objects.filter(pk__in=delete_cover_pks)
        delete_count, _ = delete_qs.delete()
        logger.warning(
            f"Delete {delete_count} CustomCovers that could not be re-sourced after config dir change."
        )


def create_missing_auth_tokens():
    """Create missing auth tokens."""
    num_created = 0
    for user in User.objects.all():
        _, created = Token.objects.get_or_create(user=user)
        if created:
            num_created += 1
        logger.info(f"Created {num_created} missing auth tokens for users.")


def ensure_db_rows():
    """Ensure database content is good."""
    ensure_superuser()
    init_admin_flags()
    init_timestamps()
    init_librarian_statuses()
    clear_library_status()
    init_custom_cover_dir()
    update_custom_covers_for_config_dir()
    create_missing_auth_tokens()


def codex_init():
    """Initialize the database and start the daemons."""
    if not ensure_db_schema():
        return False
    ensure_db_rows()
    patch_registration_setting()
    cache.clear()
    logger.info(f"root_path: {HYPERCORN_CONFIG.root_path}")
    if HYPERCORN_CONFIG.use_reloader:
        logger.info(f"Will reload hypercorn if {HYPERCORN_CONFIG_TOML} changes")
    if AUTH_REMOTE_USER:
        logger.info("Remote User authorization enabled.")
    return True
