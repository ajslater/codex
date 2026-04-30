"""Load and merge the unified codex.toml config with environment variable overrides."""

import shutil
import tomllib
from collections.abc import Mapping, MutableMapping
from os import environ
from pathlib import Path

from loguru import logger

from codex.settings.hypercorn_migrate import migrate_hypercorn_config

# Environment variable name to TOML key path mapping
# Keys listed here can be overridden by setting the corresponding env var.
_ENV_OVERRIDES: dict[str, str] = {
    # Server
    "GRANIAN_HOST": "server.host",
    "GRANIAN_PORT": "server.port",
    "GRANIAN_WORKERS": "server.workers",
    "GRANIAN_HTTP": "server.http",
    "GRANIAN_WEBSOCKETS": "server.websockets",
    "GRANIAN_URL_PATH_PREFIX": "server.url_path_prefix",
    # Logging
    "LOGLEVEL": "logging.loglevel",
    "CODEX_LOG_RETENTION": "logging.log_retention",
    "LOG_RETENTION": "logging.log_retention",  # Old
    "CODEX_LOG_TO_CONSOLE": "logging.log_to_console",
    "CODEX_LOG_TO_FILE": "logging.log_to_file",
    "CODEX_LOG_DIR": "logging.log_dir",
    # Cache
    "CODEX_CACHE_DIR": "cache.dir",
    # Import
    "CODEX_IMPORTER_LINK_FK_BATCH_SIZE": "importer.link_fk_batch_size",
    "CODEX_IMPORTER_LINK_M2M_BATCH_SIZE": "importer.link_m2m_batch_size",
    "CODEX_IMPORTER_DELETE_MAX_CHUNK_SIZE": "importer.delete_max_chunk_size",
    "CODEX_IMPORTER_SEARCH_SYNC_BATCH_MEMORY_RATIO": "importer.search_sync_batch_memory_ratio",
    "CODEX_IMPORTER_FILTER_BATCH_SIZE": "browser.filter_batch_size",
    # Importer Old
    "CODEX_LINK_FK_BATCH_SIZE": "importer.link_fk_batch_size",  # Old
    "CODEX_LINK_M2M_BATCH_SIZE": "importer.link_m2m_batch_size",  # Old
    "CODEX_DELETE_MAX_CHUNK_SIZE": "importer.delete_max_chunk_size",  # Old
    "CODEX_SEARCH_SYNC_BATCH_MEMORY_RATIO": "importer.search_sync_batch_memory_ratio",  # Old
    "CODEX_FILTER_BATCH_SIZE": "browser.filter_batch_size",  # Old
    # Browser
    "CODEX_BROWSER_MAX_OBJ_PER_PAGE": "browser.max_obj_per_page",
    "CODEX_MAX_OBJ_PER_PAGE": "browser.max_obj_per_page",  # Old
    # Throttle
    "CODEX_THROTTLE_ANON": "throttle.anon",
    "CODEX_THROTTLE_USER": "throttle.user",
    "CODEX_THROTTLE_OPDS": "throttle.opds",
    "CODEX_THROTTLE_OPENSEARCH": "throttle.opensearch",
    # Auth
    "CODEX_AUTH_REMOTE_USER": "auth.remote_user",
    # Debug
    "CODEX_DEBUG_LOG_AUTH_HEADERS": "debug.log_auth_headers",
    "CODEX_DEBUG_SLOW_QUERY_LIMIT": "debug.slow_query_limit",
    "CODEX_DEBUG_LOG_RESPONSE_TIME": "debug.log_response_time",
    "CODEX_DEBUG_LOG_REQUEST": "debug.log_request",
    # Old Debug
    "CODEX_LOG_AUTH_HEADERS": "debug.log_auth_headers",
    "CODEX_SLOW_QUERY_LIMIT": "debug.slow_query_limit",
    "CODEX_LOG_RESPONSE_TIME": "debug.log_response_time",
    "CODEX_LOG_REQUEST": "debug.log_request",
}


def _deep_get(data: Mapping, keypath: str, default=None):
    """Traverse nested dicts by a tuple of keys."""
    current = data
    keys = keypath.split(".")
    for key in keys:
        if not isinstance(current, Mapping):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _deep_set(data: MutableMapping, keypath: str, value) -> None:
    """Set a value in a nested dict, creating intermediate dicts as needed."""
    keys = keypath.split(".")
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value


def _ensure_config(config_toml: Path, config_toml_default: Path) -> None:
    """Ensure that a valid config exists."""
    if not config_toml.exists():
        migrate_hypercorn_config(config_toml, config_toml_default)
    if not config_toml.exists():
        config_toml.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(config_toml_default, config_toml)
        logger.info(f"Copied default config to {config_toml}")


def _apply_env_overrides(config: MutableMapping) -> None:
    """Apply environment variable overrides on top of the TOML values."""
    for env_name, keypath in _ENV_OVERRIDES.items():
        env_val = environ.get(env_name)
        if env_val is not None:
            _deep_set(config, keypath, env_val)


def load_codex_config(config_toml: Path, config_toml_default: Path) -> Mapping:
    """Load the unified codex config from TOML, then overlay env vars."""
    _ensure_config(config_toml, config_toml_default)
    with config_toml.open("rb") as fh:
        config = tomllib.load(fh)
    _apply_env_overrides(config)
    return config


# Convenience typed accessors


def get_str(config: Mapping, keypath: str, default: str = "") -> str:
    """Get a string value from the config."""
    val = _deep_get(config, keypath, default)
    return str(val) if val is not None else default


def get_int(config: Mapping, keypath: str, default: int = 0) -> int:
    """Get an integer value from the config."""
    val = _deep_get(config, keypath, default)
    return int(val)  # pyright: ignore[reportArgumentType]


def get_float(config: Mapping, keypath: str, default: float = 0.0) -> float:
    """Get a float value from the config."""
    val = _deep_get(config, keypath, default)
    return float(val)  # pyright: ignore[reportArgumentType]


def get_bool(config: Mapping, keypath: str, *, default: bool = False) -> bool:
    """Get a boolean value from the config."""
    val = _deep_get(config, keypath)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() not in {"", "false", "0", "no"}
    return bool(val)
