"""Logging settings functions."""
import logging
from os import environ


def get_loglevel(debug):
    """Get the loglevel for the environment."""
    loglevel = environ.get("LOGLEVEL")
    if loglevel:
        if loglevel == "VERBOSE":
            environ["LOGLEVEL"] = "INFO"
            loglevel = logging.INFO
            print(
                "LOGLEVEL=VERBOSE has been deprecated."
                " Setting LOGLEVEL to INFO (the default)."
                " Use DEBUG for more verbose logging."
            )
        return loglevel
    return logging.DEBUG if debug else logging.INFO
