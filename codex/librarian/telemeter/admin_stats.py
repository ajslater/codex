"""
Anonymous stats for admin configuration.

Everything here is a count, a boolean or a value from a closed vocabulary.
Nothing an administrator typed may leave the process: no credentials (the
encrypted fields), no urls or hostnames, no filesystem paths, no group,
provider or account names, no banner text and no api key. Where the useful
signal is "did they configure this at all", report a ``*_set`` boolean
instead of the value.
"""

from types import MappingProxyType
from typing import Any, Final

from comicbox.formats.base.online import SOURCE_NAMES
from django.conf import settings

from codex.choices.admin import AdminFlagChoices
from codex.collection import Collection
from codex.models.admin import (
    AdminFlag,
    ComicboxTaggingDefaults,
    EmailSettings,
    OIDCSettings,
    ThrottleSettings,
)
from codex.models.auth import GroupAuth, UserAuth
from codex.settings.db import (
    get_email_settings,
    get_oidc_settings,
    get_throttle_settings,
    oidc_enabled,
)

_OTHER: Final = "other"

# Flags whose signal is the on/off toggle.
_FLAG_BOOLS: Final = MappingProxyType(
    {
        AdminFlagChoices.AUTO_UPDATE.value: "auto_update",
        AdminFlagChoices.FOLDER_VIEW.value: "folder_view",
        AdminFlagChoices.IMPORT_METADATA.value: "import_metadata",
        AdminFlagChoices.LAZY_IMPORT_METADATA.value: "lazy_import_metadata",
        AdminFlagChoices.NON_USERS.value: "non_users",
        AdminFlagChoices.REGISTRATION.value: "registration",
        AdminFlagChoices.REGISTER_VERIFICATION.value: "register_verification",
        AdminFlagChoices.SEND_TELEMETRY.value: "send_telemetry",
    }
)
# Flags carrying a secret or admin-authored string. Only "is it set" ships.
_FLAG_SET_ONLY: Final = MappingProxyType(
    {
        AdminFlagChoices.API_KEY.value: "api_key_set",
        AdminFlagChoices.BANNER_TEXT.value: "banner_text_set",
    }
)
# Flags whose value is a number.
_FLAG_INTS: Final = MappingProxyType(
    {
        AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value: "browser_max_obj_per_page",
        AdminFlagChoices.CUSTOM_COVER_MAX_UPLOAD_MB.value: "custom_cover_max_upload_mb",
    }
)
# Flags whose value is a collection name.
_FLAG_COLLECTIONS: Final = MappingProxyType(
    {
        AdminFlagChoices.BROWSER_DEFAULT_COLLECTION.value: (
            "browser_default_collection"
        ),
    }
)
# Flags whose signal is their AgeRatingMetron row. That table is a fixed
# lookup seeded by migration, so its names are a closed vocabulary.
_FLAG_AGE_RATINGS: Final = MappingProxyType(
    {
        AdminFlagChoices.AGE_RATING_DEFAULT.value: "age_rating_default",
        AdminFlagChoices.ANONYMOUS_USER_AGE_RATING.value: "anonymous_user_age_rating",
    }
)
_COLLECTION_VALUES: Final = frozenset(member.value for member in Collection)
# The closed set of OIDC client authentication methods. Anything else is an
# admin typo or a provider we don't know about; report it as "other".
_TOKEN_AUTH_METHODS: Final = frozenset(
    {
        "",
        "client_secret_basic",
        "client_secret_post",
        "client_secret_jwt",
        "private_key_jwt",
        "none",
    }
)
_OIDC_BOOLS: Final = (
    "create_users",
    "link_by_email",
    "sync_groups",
    "pkce",
    "fetch_userinfo",
    "rp_initiated_logout",
)
# Claim & scope settings are admin-authored strings. Report only whether they
# differ from the shipped default.
_OIDC_CUSTOM_STRINGS: Final = ("scope", "username_claim", "groups_claim")
_THROTTLE_SCOPES: Final = ("anon", "user", "opds", "opensearch", "reset_password")


def _safe_int(value: str) -> int | None:
    """Parse an admin flag's numeric value."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _add_flag(stats: dict[str, Any], flag: AdminFlag) -> None:
    """Add one admin flag to the stats, by category."""
    if name := _FLAG_BOOLS.get(flag.key):
        stats[name] = flag.on
    elif name := _FLAG_SET_ONLY.get(flag.key):
        stats[name] = bool(flag.value)
    elif name := _FLAG_INTS.get(flag.key):
        stats[name] = _safe_int(flag.value)
    elif name := _FLAG_COLLECTIONS.get(flag.key):
        stats[name] = flag.value if flag.value in _COLLECTION_VALUES else _OTHER
    elif name := _FLAG_AGE_RATINGS.get(flag.key):
        stats[name] = flag.age_rating_metron.name if flag.age_rating_metron else ""


def get_admin_flag_stats() -> dict[str, Any]:
    """Report every admin flag, in one query."""
    stats: dict[str, Any] = {}
    for flag in AdminFlag.objects.select_related("age_rating_metron"):
        _add_flag(stats, flag)
    return stats


def _default_sources(defaults: ComicboxTaggingDefaults) -> dict[str, int]:
    """Report which online tagging sources are enabled, as a 1/absent bucket."""
    sources = defaults.default_sources
    if not isinstance(sources, list):
        return {}
    return {source: 1 for source in SOURCE_NAMES if source in sources}


def get_tagging_stats() -> dict[str, Any]:
    """Report the online tagging defaults. Never the credentials."""
    defaults = ComicboxTaggingDefaults.objects.first()
    if not defaults:
        return {}
    formats = defaults.default_formats
    return {
        "default_match_mode": defaults.default_match_mode,
        "default_prompts_mode": defaults.default_prompts_mode,
        "merge_all_sources": defaults.merge_all_sources,
        "delete_original": defaults.delete_original,
        "rename_files": defaults.rename_files,
        "default_sources": _default_sources(defaults),
        "default_format_count": len(formats) if isinstance(formats, list) else 0,
        "has_metron_credentials": bool(
            defaults.metron_key or (defaults.metron_user and defaults.metron_password)
        ),
        "has_comicvine_credentials": bool(defaults.comicvine_key),
    }


def _is_custom(oidc: OIDCSettings, field: str) -> bool:
    """Compare a string setting against the shipped default."""
    default = OIDCSettings._meta.get_field(field).get_default()
    return getattr(oidc, field) != default


def _add_oidc_stats(stats: dict[str, Any], oidc: OIDCSettings) -> None:
    """Report the OIDC client configuration, minus everything identifying."""
    stats["oidc_enabled"] = oidc_enabled(oidc)
    for field in _OIDC_BOOLS:
        stats[f"oidc_{field}"] = getattr(oidc, field)
    for field in _OIDC_CUSTOM_STRINGS:
        stats[f"oidc_{field}_custom"] = _is_custom(oidc, field)
    method = oidc.token_auth_method
    stats["oidc_token_auth_method"] = (
        method if method in _TOKEN_AUTH_METHODS else _OTHER
    )
    stats["oidc_admin_group_set"] = bool(oidc.admin_group)


def get_auth_stats() -> dict[str, Any]:
    """Report single sign on config and the age rating restrictions in use."""
    stats: dict[str, Any] = {}
    if oidc := get_oidc_settings():
        _add_oidc_stats(stats, oidc)
    stats["user_age_ceiling_count"] = UserAuth.objects.exclude(
        age_rating_metron=None
    ).count()
    stats["auth_group_exclude_count"] = GroupAuth.objects.filter(exclude=True).count()
    return stats


def get_email_stats() -> dict[str, Any]:
    """Report whether outbound email works. Never the host or addresses."""
    email: EmailSettings | None = get_email_settings()
    if not email:
        return {}
    return {
        "smtp_configured": bool(email.host and email.from_address),
        "smtp_use_tls": email.use_tls,
        "smtp_use_ssl": email.use_ssl,
    }


def get_throttle_stats() -> dict[str, Any]:
    """Report the rate limits. 0 means the scope is unthrottled."""
    throttle: ThrottleSettings | None = get_throttle_settings()
    if not throttle:
        return {}
    return {f"throttle_{scope}": getattr(throttle, scope) for scope in _THROTTLE_SCOPES}


def get_deployment_stats() -> dict[str, Any]:
    """Report deployment shape from codex.toml. Never a path or a prefix."""
    return {
        "remote_user_auth": bool(settings.AUTH_REMOTE_USER),
        "failed_login_log": bool(settings.AUTH_FAILED_LOGIN_LOG),
        "failed_login_log_trust_forwarded_for": bool(
            settings.AUTH_FAILED_LOGIN_LOG_TRUST_FORWARDED_FOR
        ),
        "url_path_prefix_set": bool(settings.GRANIAN_URL_PATH_PREFIX),
    }
