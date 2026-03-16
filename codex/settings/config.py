"""Load and merge the unified codex.toml config with environment variable overrides."""

import shutil
import sys
from os import environ
from pathlib import Path

from loguru import logger

if sys.version_info >= (3, 11):
    import tomllib  # pyright: ignore[reportUnreachable]
else:
    try:
        import tomllib  # ty: ignore[unresolved-import]
    except ModuleNotFoundError:
        import tomli as tomllib
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
    "CODEX_ROOT_PATH": "server.url.root_path",
    # Logging
    "LOGLEVEL": "logging.loglevel",
    "LOG_RETENTION": "logging.log_retention",
    "CODEX_LOG_TO_CONSOLE": "logging.log_to_console",
    "CODEX_LOG_TO_FILE": "logging.log_to_file",
    # Import
    "CODEX_MAX_IMPORT_BATCH_SIZE": "import.max_import_batch_size",
    "CODEX_LINK_FK_BATCH_SIZE": "import.link_fk_batch_size",
    "CODEX_LINK_M2M_BATCH_SIZE": "import.link_m2m_batch_size",
    "CODEX_DELETE_MAX_CHUNK_SIZE": "import.delete_max_chunk_size",
    "CODEX_SEARCH_SYNC_BATCH_MEMORY_RATIO": "import.search_sync_batch_memory_ratio",
    # Browser
    "CODEX_SLOW_QUERY_LIMIT": "browser.slow_query_limit",
    "CODEX_BROWSER_MAX_OBJ_PER_PAGE": "browser.max_obj_per_page",
    "CODEX_FILTER_BATCH_SIZE": "browser.filter_batch_size",
    # Throttl
    "CODEX_THROTTLE_ANON": "throttle.anon",
    "CODEX_THROTTLE_USER": "throttle.user",
    "CODEX_THROTTLE_OPDS": "throttle.opds",
    "CODEX_THROTTLE_OPENSEARCH": "throttle.opensearch",
}


def _deep_get(data: dict, keypath: str, default=None):
    """Traverse nested dicts by a tuple of keys."""
    current = data
    keys = keypath.split(".")
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _deep_set(data: dict, keypath: str, value) -> None:
    """Set a value in a nested dict, creating intermediate dicts as needed."""
    keys = keypath.split(".")
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value


def _ensure_config(config_toml: Path, config_toml_default: Path) -> None:
    """Ensure that a valid config exists."""
    if not config_toml.exists():
        migrate_hypercorn_config(config_toml.parent, config_toml, config_toml_default)
    if not config_toml.exists():
        shutil.copy(config_toml_default, config_toml)
        logger.info(f"Copied default config to {config_toml}")


def _apply_env_overrides(config: dict) -> None:
    """Apply environment variable overrides on top of the TOML values."""
    for env_name, keypath in _ENV_OVERRIDES.items():
        env_val = environ.get(env_name)
        if env_val is not None:
            _deep_set(config, keypath, env_val)


def load_codex_config(config_toml: Path, config_toml_default: Path) -> dict:
    """Load the unified codex config from TOML, then overlay env vars."""
    _ensure_config(config_toml, config_toml_default)
    with config_toml.open("rb") as fh:
        config = tomllib.load(fh)
    _apply_env_overrides(config)
    return config


# Convenience typed accessors


def get_str(config: dict, keypath: str, default: str = "") -> str:
    """Get a string value from the config."""
    val = _deep_get(config, keypath, default)
    return str(val) if val is not None else default


def get_int(config: dict, keypath: str, default: int = 0) -> int:
    """Get an integer value from the config."""
    val = _deep_get(config, keypath, default)
    return int(val)  # pyright: ignore[reportArgumentType]


def get_float(config: dict, keypath: str, default: float = 0.0) -> float:
    """Get a float value from the config."""
    val = _deep_get(config, keypath, default)
    return float(val)  # pyright: ignore[reportArgumentType]


def get_bool(config: dict, keypath: str, *, default: bool = False) -> bool:
    """Get a boolean value from the config."""
    val = _deep_get(config, keypath)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() not in {"", "false", "0", "no"}
    return bool(val)
