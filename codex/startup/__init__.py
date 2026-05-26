"""Initialize Codex Dataabse before running."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.db.models.functions import Now
from loguru import logger
from rest_framework.authtoken.models import Token

from codex.choices.admin import AdminFlagChoices
from codex.librarian.status_controller import STATUS_DEFAULTS
from codex.models import (
    AdminFlag,
    AgeRatingMetron,
    LibrarianStatus,
    Library,
    Timestamp,
)
from codex.models.age_rating import (
    ALL_METRON_RATINGS,
    ANONYMOUS_USER_DEFAULT_AGE_RATING,
    DEFAULT_AGE_RATING,
    invalidate_metron_index_cache,
)
from codex.settings import (
    AUTH_REMOTE_USER,
    BROWSER_MAX_OBJ_PER_PAGE,
    CODEX_CONFIG_TOML,
    CUSTOM_COVERS_MAX_UPLOAD_MB,
    DEBUG,
    GRANIAN_URL_PATH_PREFIX,
    RESET_ADMIN,
)
from codex.startup.db import ensure_db_schema
from codex.startup.registration import patch_registration_setting
from codex.views.admin.api_key import _new_api_key


def ensure_superuser() -> None:
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


def _delete_orphans(model, field, names) -> None:
    """Delete orphans for declared models."""
    params = {f"{field}__in": names}
    query = model.objects.filter(~Q(**params))
    count, _ = query.delete()
    if count:
        logger.info(f"Deleted {count} orphan {model._meta.verbose_name_plural}.")


def init_admin_flags() -> None:
    """
    Init admin flag rows.

    The two age-rating flags (``AA``/``AR``) seed with an FK to an
    :class:`AgeRatingMetron` row — the typed equivalent of the old
    ``value`` string. The migration does this on first install; this
    covers the edge case where an admin deletes the row entirely so
    startup can heal it with a sensible default rather than a bare
    row with a NULL FK.

    Requires :func:`init_age_rating_metron` to have run first so the
    FK targets exist.
    """
    _delete_orphans(AdminFlag, "key", AdminFlagChoices.values)

    age_rating_defaults = {
        AdminFlagChoices.ANONYMOUS_USER_AGE_RATING.value: (
            ANONYMOUS_USER_DEFAULT_AGE_RATING
        ),
        AdminFlagChoices.AGE_RATING_DEFAULT.value: DEFAULT_AGE_RATING,
    }
    # Initial ``value`` strings for flags that ship with a non-empty
    # default. Heals the row to a sensible state if an admin deletes
    # it; the migration that introduced the flag does the same insert.
    value_defaults = {
        # Mirrors the ``SettingsBrowser.top_group`` model default so
        # ``admin_default_route_for("p")`` resolves to the historical
        # ``DEFAULT_BROWSER_ROUTE`` (``/r/0/1``) — upgrade-day no-op.
        AdminFlagChoices.BROWSER_DEFAULT_GROUP.value: "p",
        # Migrated from TOML at first boot of the new version;
        # the value reflects the live settings constant so deleted
        # rows heal back to the operator's configured value.
        AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value: str(BROWSER_MAX_OBJ_PER_PAGE),
        AdminFlagChoices.CUSTOM_COVER_MAX_UPLOAD_MB.value: str(
            CUSTOM_COVERS_MAX_UPLOAD_MB
        ),
    }
    # Resolve seed FK targets in one query.
    metron_by_name = {
        name: pk
        for pk, name in AgeRatingMetron.objects.filter(
            name__in=age_rating_defaults.values()
        ).values_list("pk", "name")
    }
    for key, title in AdminFlagChoices.choices:
        # ``defaults`` spans ``bool`` (``on``), ``str`` (``value``) and
        # the optional FK id (``age_rating_metron_id``) — annotate so
        # the conditional inserts don't narrow pyright's inferred type.
        defaults: dict[str, bool | int | str | None] = {
            "on": key not in AdminFlag.FALSE_DEFAULTS,
        }
        if key in age_rating_defaults:
            defaults["age_rating_metron_id"] = metron_by_name.get(
                age_rating_defaults[key]
            )
        if key in value_defaults:
            defaults["value"] = value_defaults[key]
        flag, created = AdminFlag.objects.get_or_create(defaults=defaults, key=key)
        # The API key row holds the actual key in ``value``. Heal here
        # so fresh installs and admin-deleted rows both come back with
        # a usable token; the 0051 migration handles upgrades.
        if key == AdminFlagChoices.API_KEY.value and not flag.value:
            flag.value = _new_api_key()
            flag.save()
        if created:
            logger.info(f"Created AdminFlag: {title} = {flag.on}")


def init_age_rating_metron() -> None:
    """
    Ensure every MetronAgeRatingEnum value has an AgeRatingMetron row.

    Idempotent — reasserts the canonical lookup table on every codex boot.
    Never deletes orphans; AgeRating.metron uses on_delete=SET_NULL so an
    externally-deleted row simply nulls the FK until re-import heals it.

    Clears the in-process ``pk → index`` cache consumed by
    :func:`codex.models.age_rating.get_metron_index` so that boots
    following a seed change (new enum value, migration rerun) pick up
    the refreshed mapping on the next Comic ``presave``.
    """
    for name, index in ALL_METRON_RATINGS:
        _, created = AgeRatingMetron.objects.update_or_create(
            name=name, defaults={"index": index}
        )
        if created:
            logger.info(f"Created AgeRatingMetron: {name} ({index})")
    invalidate_metron_index_cache()


def init_timestamps() -> None:
    """Init timestamps."""
    _delete_orphans(Timestamp, "key", Timestamp.Choices.values)

    for enum in Timestamp.Choices:
        key = enum.value
        ts, created = Timestamp.objects.get_or_create(key=key)
        if created:
            label = Timestamp.Choices(ts.key).label
            logger.debug(f"Created {label} timestamp.")


def init_librarian_statuses() -> None:
    """Init librarian statuses."""
    # Remove old statuses from previous versions of codex.
    _delete_orphans(
        LibrarianStatus,
        "status_type",
        LibrarianStatus.StatusChoices.values,
    )

    # Create any missing statuses with defaults.
    for status_type, title in LibrarianStatus.StatusChoices.choices:
        _, created = LibrarianStatus.objects.get_or_create(
            defaults=STATUS_DEFAULTS, status_type=status_type
        )
        if created:
            logger.debug(f"Created {title} LibrarianStatus.")

    # Reset any statuses left in a non-default state (jobs interrupted by
    # shutdown) without touching statuses already at defaults.
    # This ensures that updated_at is preserved across restarts.
    non_default_filter = (
        Q(preactive__isnull=False)
        | Q(active__isnull=False)
        | Q(complete__isnull=False)
        | Q(total__isnull=False)
        | ~Q(subtitle="")
    )
    if count := LibrarianStatus.objects.filter(non_default_filter).update(
        **STATUS_DEFAULTS, updated_at=Now()
    ):
        logger.debug(f"Reset {count} interrupted LibrarianStatuses to defaults.")


def init_libraries() -> None:
    """Reset libraries that were mid-update when the server stopped."""
    lib_count = Library.objects.filter(update_in_progress=True).update(
        update_in_progress=False, updated_at=Now()
    )
    if lib_count:
        logger.debug(f"Reset {lib_count} Libraries' update_in_progress flag.")


def create_missing_auth_tokens() -> None:
    """Create missing auth tokens."""
    num_created = 0
    for user in User.objects.all():
        _, created = Token.objects.get_or_create(user=user)
        if created:
            num_created += 1
        logger.info(f"Created {num_created} missing auth tokens for users.")


def ensure_db_rows() -> None:
    """Ensure database content is good."""
    ensure_superuser()
    # AgeRatingMetron rows must exist before AdminFlag seeds FK targets.
    init_age_rating_metron()
    init_admin_flags()
    init_timestamps()
    init_librarian_statuses()
    init_libraries()
    create_missing_auth_tokens()


def codex_init() -> bool:
    """Initialize the database and start the daemons."""
    if not ensure_db_schema():
        return False
    ensure_db_rows()
    patch_registration_setting()
    cache.clear()
    if GRANIAN_URL_PATH_PREFIX:
        path_prefix_log = (
            f"Codex is being served from url path prefix: {GRANIAN_URL_PATH_PREFIX}"
        )
    else:
        path_prefix_log = "Codex is being served without a url path prefix."
    logger.info(path_prefix_log)
    if DEBUG:
        logger.info(f"Will reload granian if {CODEX_CONFIG_TOML} changes")
    if AUTH_REMOTE_USER:
        logger.info("Remote User authorization enabled.")
    return True
