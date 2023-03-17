"""Parse the hypercorn config for settings."""
import shutil

from hypercorn.config import Config

from codex.memory import get_mem_limit

AUTO_IMPORT_BATCH_SIZE = "auto"
MAX_IMPORT_BATCH_SIZE_DEFAULT = AUTO_IMPORT_BATCH_SIZE


def _ensure_config(hypercon_config_toml, hypercorn_config_toml_default):
    """Ensure that a valid config exists."""
    if not hypercon_config_toml.exists():
        shutil.copy(hypercorn_config_toml_default, hypercon_config_toml)
        print(f"Copied default config to {hypercon_config_toml}")


def _get_max_import_batch_size(config):
    max_import_batch_size = getattr(
        config, "max_import_batch_size", MAX_IMPORT_BATCH_SIZE_DEFAULT
    )
    if max_import_batch_size == AUTO_IMPORT_BATCH_SIZE:
        mem_limit_gb = get_mem_limit("g")
        max_items = 5000 * int(mem_limit_gb)
    else:
        max_items = max(1, int(max_import_batch_size))
    return max_items


def load_hypercorn_config(hypercorn_config_toml, hypercorn_config_toml_default, debug):
    """Load the hypercorn config."""
    _ensure_config(hypercorn_config_toml, hypercorn_config_toml_default)
    config = Config.from_toml(hypercorn_config_toml)
    if debug:
        config.use_reloader = True
    max_import_batch_size = _get_max_import_batch_size(config)
    return config, max_import_batch_size
