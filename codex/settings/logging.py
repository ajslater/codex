"""Logging Settings."""

from logging import Handler
from typing import override

from loguru import logger


class LoguruHandler(Handler):
    """Redirect logging to loguru."""

    @override
    def emit(self, record):
        """Emit loguru logs."""
        try:
            level = logger.level(record.levelname).name
        except Exception:
            level = record.levelno

        logger.opt(
            depth=6,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def get_logging_settings(loglevel: str | int, *, debug: bool) -> dict[str, int | dict]:
    """Get logging for settings."""
    loggers: dict[str, dict] = {
        "watchfiles.main": {
            # DEBUG logs from watchfiles include a 5 second timeout
            "level": "INFO",
            "propagate": False,
        },
    }
    if loglevel != "TRACE":
        loggers.update(
            {
                "asyncio": {
                    "level": "INFO",
                },
                # Granian's Rust core emits DEBUG noise for routine
                # WebSocket close frames (a client disconnecting fires
                # "Received close frame" + "Replying to close"). Not
                # actionable; visible only at TRACE.
                #
                # ``_granian`` covers the granian crate; ``tungstenite``
                # and ``tokio_tungstenite`` cover the underlying WS
                # crates that emit the ``Received close frame`` /
                # ``Replying to close`` / ``Sending after closing is
                # not allowed`` messages directly. pyo3-log maps Rust
                # ``::`` separators to Python ``.`` so these names
                # apply hierarchically to all submodules.
                "_granian": {
                    "level": "INFO",
                },
                "tungstenite": {
                    "level": "INFO",
                },
                "tokio_tungstenite": {
                    "level": "INFO",
                },
            }
        )
    if not debug:
        loggers.update(
            {
                "urllib3.connectionpool": {"level": "INFO"},
                "PIL": {
                    "level": "INFO",
                },
            }
        )
    level = "DEBUG" if loglevel == "TRACE" else loglevel
    return {
        "version": 1,
        "disable_existing_loggers": True,
        "handlers": {
            "loguru": {
                "class": "codex.settings.logging.LoguruHandler",
            },
        },
        "root": {
            "handlers": ["loguru"],
            "level": level,
            "propagate": True,
        },
        "django": {
            "handlers": ["loguru"],
            "level": level,
            "propagate": True,
        },
        "django.request": {
            "handlers": ["loguru"],
            "level": level,
            "propagate": True,
        },
        "django.server": {
            "handlers": ["loguru"],
            "level": level,
            "propagate": True,
        },
        "loggers": loggers,
    }
