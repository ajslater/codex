"""Initialize logging for codex."""

import sys
from typing import Any

from loguru import logger

from codex.settings import (
    AUTH_FAILED_LOGIN_LOG,
    AUTH_FAILED_LOGIN_LOG_PATH,
    DEBUG,
    LOG_PATH,
    LOG_RETENTION,
    LOG_ROTATION,
    LOGLEVEL,
)


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

    # Privacy: when the failed-login feature is on, the dedicated sink
    # receives the IP-bearing lines and the main sinks drop them. When
    # off, nothing carries the tag and the inverse filter would be a
    # no-op anyway, so don't bother attaching it. Lazy import keeps the
    # failed_login_log module out of the graph when the feature is off.
    main_filter = None
    if AUTH_FAILED_LOGIN_LOG:
        from codex.failed_login_log import not_failed_login_filter

        main_filter = not_failed_login_filter

    logger.add(sys.stdout, **kwargs, colorize=True, filter=main_filter)
    logger.add(
        LOG_PATH,
        **kwargs,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression="xz",
        filter=main_filter,
    )
    if AUTH_FAILED_LOGIN_LOG:
        from codex.failed_login_log import failed_login_filter

        AUTH_FAILED_LOGIN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            AUTH_FAILED_LOGIN_LOG_PATH,
            format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
            level="WARNING",
            rotation=LOG_ROTATION,
            retention=LOG_RETENTION,
            compression="xz",
            enqueue=True,
            filter=failed_login_filter,
        )
