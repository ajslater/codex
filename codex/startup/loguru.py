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
from codex.settings.logging import scrub_secrets_filter


def _main_sink_filter(record) -> bool:
    """
    Scrub secrets; drop failed-login IP lines when their dedicated sink is on.

    Defined at module level so loguru's multiprocessing enqueue can pickle
    it; a closure over ``AUTH_FAILED_LOGIN_LOG`` would fail to pickle when
    the librarian daemon process spawns.
    """
    scrub_secrets_filter(record)
    if not AUTH_FAILED_LOGIN_LOG:
        return True
    from codex.failed_login_log import not_failed_login_filter

    return not_failed_login_filter(record)


def _failed_login_sink_filter(record) -> bool:
    """Scrub secrets and apply the failed-login filter for its dedicated sink."""
    scrub_secrets_filter(record)
    from codex.failed_login_log import failed_login_filter

    return failed_login_filter(record)


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

    # ``_main_sink_filter`` always scrubs secrets so API keys never reach
    # the main sinks; it also drops IP-bearing failed-login lines when
    # the dedicated sink is on so those land only in that file. Both
    # filter helpers are defined at module level for picklability —
    # loguru's ``enqueue=True`` pickles handlers when the librarian
    # multiprocessing daemon spawns.
    logger.add(sys.stdout, **kwargs, colorize=True, filter=_main_sink_filter)
    logger.add(
        LOG_PATH,
        **kwargs,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression="xz",
        filter=_main_sink_filter,
    )
    if AUTH_FAILED_LOGIN_LOG:
        AUTH_FAILED_LOGIN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            AUTH_FAILED_LOGIN_LOG_PATH,
            format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
            level="WARNING",
            rotation=LOG_ROTATION,
            retention=LOG_RETENTION,
            compression="xz",
            enqueue=True,
            filter=_failed_login_sink_filter,
        )
