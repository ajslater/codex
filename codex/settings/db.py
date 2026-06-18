"""
DB-backed runtime settings.

Settings consumed at request time can be overridden in the Admin UI. The
precedence is **DB row → Django settings (TOML → env → default)**.

The TOML/env/default layer is loaded once at boot into
:mod:`django.conf.settings`; the DB layer is read live via the helpers
here. The ORM reads are caught by django-cachalot, which invalidates the
cached row whenever a row in the same table is written — so a save in
the Admin UI is visible on the next request without manual cache
juggling.

Each helper imports its model lazily because this module is imported
from settings consumers that may load before Django apps are ready (the
import becomes a no-op until the registry is populated).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings

from codex.choices.admin import AdminFlagChoices

if TYPE_CHECKING:
    from codex.models.admin import AdminFlag, EmailSettings, ThrottleSettings

THROTTLE_SCOPE_PERIOD: dict[str, str] = {
    "anon": "min",
    "user": "min",
    "opds": "min",
    "opensearch": "min",
    "reset_password": "hour",
}


def _get_admin_flag(key: str) -> AdminFlag | None:
    """Return the AdminFlag row for ``key`` or None when missing/unmigrated."""
    try:
        from codex.models.admin import AdminFlag
    except (ImportError, RuntimeError):
        return None
    try:
        return AdminFlag.objects.filter(key=key).first()
    except Exception:
        return None


def get_admin_flag_int(key: str, default: int) -> int:
    """
    Read an int from an :class:`AdminFlag` ``value`` column.

    Falls back to ``default`` when the row is missing, the value is
    empty, or the value does not parse as int.
    """
    flag = _get_admin_flag(key)
    if flag is None or not flag.value:
        return default
    try:
        return int(flag.value)
    except (TypeError, ValueError):
        return default


def get_browser_max_obj_per_page() -> int:
    """Runtime browser page size — DB ``MP`` flag, falling back to settings."""
    return get_admin_flag_int(
        AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value,
        default=settings.BROWSER_MAX_OBJ_PER_PAGE,
    )


def get_custom_cover_max_upload_mb() -> int:
    """Runtime custom-cover upload cap (MB) — DB ``CM`` flag, falling back to settings."""
    return get_admin_flag_int(
        AdminFlagChoices.CUSTOM_COVER_MAX_UPLOAD_MB.value,
        default=settings.CUSTOM_COVERS_MAX_UPLOAD_MB,
    )


def get_custom_cover_max_upload_bytes() -> int:
    """Runtime custom-cover upload cap in bytes."""
    return get_custom_cover_max_upload_mb() * 1024 * 1024


def get_email_settings() -> EmailSettings | None:
    """Return the EmailSettings singleton or None when DB isn't ready."""
    try:
        from codex.models.admin import EmailSettings
    except (ImportError, RuntimeError):
        return None
    try:
        return EmailSettings.objects.filter(pk=1).first()
    except Exception:
        return None


def _coalesce(db_value: Any, settings_value: Any) -> Any:
    """Prefer ``db_value`` when truthy; otherwise fall back to ``settings_value``."""
    return db_value or settings_value


def get_email_connection_kwargs() -> dict[str, Any]:
    """
    Return kwargs to pass to :class:`django.core.mail.backends.smtp.EmailBackend`.

    Pulls each field from the DB row first, falling back to the
    matching Django setting (which itself sources from TOML / env /
    default). Boolean toggles use ``getattr`` so a missing row doesn't
    crash callers.
    """
    db = get_email_settings()
    if db is None:
        return {
            "host": settings.EMAIL_HOST,
            "port": settings.EMAIL_PORT,
            "username": settings.EMAIL_HOST_USER,
            "password": settings.EMAIL_HOST_PASSWORD,
            "use_tls": settings.EMAIL_USE_TLS,
            "use_ssl": settings.EMAIL_USE_SSL,
            "timeout": settings.EMAIL_TIMEOUT,
        }
    return {
        "host": _coalesce(db.host, settings.EMAIL_HOST),
        "port": db.port or settings.EMAIL_PORT,
        "username": _coalesce(db.user, settings.EMAIL_HOST_USER),
        "password": _coalesce(db.password, settings.EMAIL_HOST_PASSWORD),
        # Booleans: explicit DB value wins (False is a real choice).
        "use_tls": db.use_tls,
        "use_ssl": db.use_ssl,
        "timeout": db.timeout or settings.EMAIL_TIMEOUT,
    }


def get_email_from_address() -> str:
    """Effective sender address with DB → settings → user fallback."""
    db = get_email_settings()
    candidates = []
    if db is not None:
        candidates.extend((db.from_address, db.user))
    candidates.extend((settings.DEFAULT_FROM_EMAIL, settings.EMAIL_HOST_USER))
    for value in candidates:
        if value:
            return value
    return ""


def get_email_subject_prefix() -> str:
    """Effective subject prefix with DB → settings fallback."""
    db = get_email_settings()
    if db is not None and db.subject_prefix:
        return db.subject_prefix
    return settings.EMAIL_SUBJECT_PREFIX


def get_throttle_settings() -> ThrottleSettings | None:
    """Return the ThrottleSettings singleton or None when DB isn't ready."""
    try:
        from codex.models.admin import ThrottleSettings
    except (ImportError, RuntimeError):
        return None
    try:
        return ThrottleSettings.objects.filter(pk=1).first()
    except Exception:
        return None


def _settings_throttle_default(scope: str) -> int:
    """Boot-time throttle value for the given scope, from TOML/env."""
    name = f"THROTTLE_{scope.upper()}"
    return getattr(settings, name, 0) or 0


def get_throttle_rate_string(scope: str) -> str | None:
    """
    DRF-compatible rate string for ``scope`` or ``None`` to disable.

    Reads :class:`ThrottleSettings` and falls back to the matching
    boot-time setting. ``0`` (or missing) returns ``None`` so DRF's
    ``SimpleRateThrottle.allow_request`` early-returns ``True`` —
    effectively disabling the limiter for that scope.
    """
    period = THROTTLE_SCOPE_PERIOD.get(scope)
    if period is None:
        return None
    db = get_throttle_settings()
    value = getattr(db, scope, None) if db is not None else None
    if value is None:
        value = _settings_throttle_default(scope)
    if not value:
        return None
    return f"{value}/{period}"


def email_enabled() -> bool:
    """
    Whether outbound email is configured well enough to attempt a send.

    Requires an effective host and an effective from-address. Feature
    gates (registration verification, password reset link) consult this
    at request time, so flipping email config in the Admin UI takes
    effect on the next request.
    """
    kwargs = get_email_connection_kwargs()
    return bool(kwargs.get("host") and get_email_from_address())
