#!/usr/bin/env python3
"""The main runnable for codex. Sets up codex and runs hypercorn."""

import sys

from loguru import logger
from typing_extensions import Any

from codex.settings import (
    LOG_PATH,
    LOG_RETENTION,
    LOG_ROTATION,
    LOGLEVEL,
)

_LOG_FMT = "{asctime} {levelname:7} {message}"
_DEBUG_LOG_FMT = "{asctime} {levelname:7} {name:25} {message}"
_LOGURU_WARNING_NO = logger.level("ERROR").no


def _log_formatter(record):
    fmt = "<lvl>{time:YYYY-MM-DD HH:mm:ss} | {level: <8}"
    if record["level"].no >= _LOGURU_WARNING_NO:
        fmt += " | </lvl>"
        fmt += "<dim><cyan>{thread.name}</cyan></dim>:"
        fmt += "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        fmt += "<lvl>"
    fmt += " | {message}</lvl>"
    fmt += "\n{exception}"
    return fmt


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
        "format": _log_formatter,
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
