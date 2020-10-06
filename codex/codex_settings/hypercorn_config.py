"""Parse the hypercorn config for settings."""
from logging import getLogger

import toml


LOG = getLogger(__name__)


def get_root_path(config_path, debug):
    """Get the root path from hypercorn config if not in debug mode."""
    root_path = ""
    if debug:
        # In debug mode Whitenoise adds the ROOT_PATH itself.
        return root_path
    hypercorn_conf_path = config_path / "hypercorn.toml"
    try:
        hypercorn_conf = toml.load(hypercorn_conf_path)
        # Get root path. Iff it exists ensure a trailing slash.

        conf_root_path = hypercorn_conf.get("root_path", "")
        root_path = conf_root_path.lstrip("/")
        # Ensure trailing slash
        if root_path and root_path[-1] != "/":
            root_path += "/"

    except Exception as exc:
        LOG.warn(f"Error getting root_path from {hypercorn_conf_path}.")
        LOG.exception(exc)
    return root_path
