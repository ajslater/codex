"""Initialize logging for codex."""

import sys
from typing import Any

from loguru import logger

from codex.settings import DEBUG, LOG_PATH, LOG_RETENTION, LOG_ROTATION, LOGLEVEL


def _log_format() -> str:
    fmt = "<lvl>{time:YYYY-MM-DD HH:mm:ss} | {level: <8}"
    if DEBUG:
        fmt += " | </lvl>"
        fmt += "<dim><cyan>{thread.name}</cyan></dim>:"
        fmt += "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        fmt += "<lvl>"
    fmt += " | {message}</lvl>"
    # fmt += "\n{exception}"  only for format as a callable
    return fmt


CODEX_LOG_FORMAT = _log_format()


def loguru_init() -> None:
    """Initialize loguru sinks."""
    logger.level("DEBUG", color="<light-black>")
    logger.level("INFO", color="<white>")
    logger.level("SUCCESS", color="<green>")

    kwargs: dict[str, Any] = {
        "backtrace": True,
        "catch": True,
        "enqueue": True,
        "format": CODEX_LOG_FORMAT,
        "level": LOGLEVEL,
    }
    logger.remove()  # Default "sys.stderr" sink is not picklable
    logger.add(sys.stdout, **kwargs, colorize=True)
    logger.add(
        LOG_PATH,
        **kwargs,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression="xz",
    )
