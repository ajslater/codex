"""Logging settings functions."""
import logging

from os import environ


def get_loglevel(debug):
    """Get the loglevel for the environment."""
    loglevel = environ.get("LOGLEVEL")
    if loglevel:
        if loglevel == "VERBOSE":
            print(
                "LOGLEVEL=VERBOSE has been deprecated. Use INFO (the default) or DEBUG."
            )
            loglevel = logging.INFO
        return loglevel
    elif debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    return log_level
