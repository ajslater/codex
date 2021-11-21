"""Parse the hypercorn config for settings."""
import shutil

from logging import getLogger

from hypercorn.config import Config


LOG = getLogger(__name__)


def _ensure_config(hypercon_config_toml, hypercorn_config_toml_default):
    """Ensure that a valid config exists."""
    if not hypercon_config_toml.exists():
        shutil.copy(hypercorn_config_toml_default, hypercon_config_toml)
        LOG.warning(f"Copied default config to {hypercon_config_toml}")


def load_hypercorn_config(hypercorn_config_toml, hypercorn_config_toml_default, debug):
    """Load the hypercorn config."""
    _ensure_config(hypercorn_config_toml, hypercorn_config_toml_default)
    config = Config.from_toml(hypercorn_config_toml)
    LOG.info(f"Loaded config from {hypercorn_config_toml}")
    if debug:
        config.use_reloader = True
        LOG.info("Will reload hypercorn if files change")
    if not hasattr(config, "max_db_ops"):
        config.max_db_ops = 100000
    config.max_db_ops = max(1, config.max_db_ops)
    LOG.verbose(f"max_db_ops limit is {config.max_db_ops}")  # type: ignore
    return config
