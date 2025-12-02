"""The main runnable for codex. Sets up codex and runs hypercorn."""

import sys
from typing import Any

from loguru import logger

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


def init_logging():
    """Initialize loguru sinks."""
    logger.level("DEBUG", color="<light-black>")
    logger.level("INFO", color="<white>")
    logger.level("SUCCESS", color="<green>")

    log_format = _log_format()
    kwargs: dict[str, Any] = {
        "backtrace": True,
        "catch": True,
        "enqueue": True,
        "format": log_format,
        "level": LOGLEVEL,
    }
    logger.remove()  # Default "sys.stderr" sink is not picklable
    logger.add(sys.stdout, **kwargs, colorize=True)  # ty: ignore[no-matching-overload]
    logger.add(
        LOG_PATH,
        **kwargs,  # ty: ignore[invalid-argument-type]
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression="xz",
    )
