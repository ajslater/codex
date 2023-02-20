"""Parse the hypercorn config for settings."""
import shutil

from hypercorn.config import Config

MAX_DB_OPS_DEFAULT = 100000


def _ensure_config(hypercon_config_toml, hypercorn_config_toml_default):
    """Ensure that a valid config exists."""
    if not hypercon_config_toml.exists():
        shutil.copy(hypercorn_config_toml_default, hypercon_config_toml)
        print(f"Copied default config to {hypercon_config_toml}")


def load_hypercorn_config(hypercorn_config_toml, hypercorn_config_toml_default, debug):
    """Load the hypercorn config."""
    _ensure_config(hypercorn_config_toml, hypercorn_config_toml_default)
    config = Config.from_toml(hypercorn_config_toml)
    if debug:
        config.use_reloader = True
    max_db_ops = max(1, int(getattr(config, "max_db_ops", MAX_DB_OPS_DEFAULT)))
    return config, max_db_ops
