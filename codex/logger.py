#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""

import sys

from loguru import logger
from typing_extensions import Any

from codex.settings import DEBUG, LOG_PATH, LOG_RETENTION, LOG_ROTATION, LOGLEVEL


def _log_format():
    fmt = "<lvl>{time:YYYY-MM-DD HH:mm:ss} | {level: <8}"
    if DEBUG:
        fmt += " | </lvl>"
        fmt += "<dim><cyan>{thread.name}</cyan></dim>:"
        fmt += "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        fmt += "<lvl>"
    fmt += " | {message}</lvl>"
    # fmt += "\n{exception}"  only for format as a callable
    return fmt


_LOG_FORMAT = _log_format()


def init_logging():
    """Initialize loguru sinks."""
    logger.level("DEBUG", color="<light-black>")
    logger.level("INFO", color="<white>")
    logger.level("SUCCESS", color="<green>")

    kwargs: dict[str, Any] = {
        "level": LOGLEVEL,
        "backtrace": True,
        "enqueue": True,
        "catch": True,
        "format": _LOG_FORMAT,
    }
    logger.remove()  # Default "sys.stderr" sink is not picklable
    logger.add(sys.stdout, **kwargs)
    logger.add(
        LOG_PATH,
        **kwargs,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression="xz",
    )
