"""Logging Settings."""

import logging
import re
from logging import Filter, Handler
from typing import Final, override

from loguru import logger

# Paths whose routine anon-403s are noise, not abuse. The first-load
# probe to ``/api/v4/auth/profile`` is the obvious offender — a fresh
# browser hits it before any session cookie exists. Django's
# BaseHandler.get_response logs every 4xx at WARNING; we downgrade the
# ones we expect so the main log stays useful.
_NOISY_FORBIDDEN_PATHS: Final[frozenset[str]] = frozenset({"/api/v4/auth/profile"})


# Query-string credentials we never want in logs. httpx logs the full
# request URL at INFO when codex bridges stdlib logging into loguru, so
# a ComicVine call leaks the ``api_key=`` value verbatim. Mokkari
# (Metron) uses HTTP Basic auth in headers — the Authorization regex
# below covers that path defensively even though httpx doesn't log
# headers today.
_SECRET_QUERY_PARAM_RE: Final = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|auth)=[^&\s\"'<>]*"
)
_AUTHORIZATION_HEADER_RE: Final = re.compile(
    r"(?i)(Authorization:\s*(?:Basic|Bearer))\s+\S+"
)
_REDACTED: Final = "<redacted>"


def scrub_secrets(message: str) -> str:
    """Mask credentials in a log message string."""
    message = _SECRET_QUERY_PARAM_RE.sub(rf"\1={_REDACTED}", message)
    return _AUTHORIZATION_HEADER_RE.sub(rf"\1 {_REDACTED}", message)


def scrub_secrets_filter(record) -> bool:
    """Loguru filter that scrubs credentials in the record's message in place."""
    record["message"] = scrub_secrets(record["message"])
    return True


class DowngradeNoisyForbiddenFilter(Filter):
    """Downgrade routine anon 403s on known-noisy paths to DEBUG."""

    @override
    def filter(self, record) -> bool:
        if record.levelno != logging.WARNING:
            return True
        msg = record.getMessage()
        if not msg.startswith("Forbidden: "):
            return True
        path = msg.split(": ", 1)[1]
        if path in _NOISY_FORBIDDEN_PATHS:
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
        return True


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
        ).log(level, scrub_secrets(record.getMessage()))


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
    # ``django.request`` belongs inside ``loggers`` so dictConfig sees it;
    # putting it at the top level (as this file used to) is silently
    # ignored. Records still reach the root ``loguru`` handler via
    # propagation, but the filter only runs when the logger is declared
    # here.
    loggers["django.request"] = {
        "filters": ["downgrade_noisy_forbidden"],
    }
    return {
        "version": 1,
        "disable_existing_loggers": True,
        "filters": {
            "downgrade_noisy_forbidden": {
                "()": "codex.settings.logging.DowngradeNoisyForbiddenFilter",
            },
        },
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
        "loggers": loggers,
    }
