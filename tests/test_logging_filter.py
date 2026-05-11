"""Tests for the noisy-Forbidden log filter."""

import logging
from typing import Final, override

from django.test import TestCase

from codex.settings.logging import DowngradeNoisyForbiddenFilter

_FILTER_NAME: Final = "test"


def _build_record(level: int, msg: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord(
        name="django.request",
        level=level,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=args,
        exc_info=None,
    )


class DowngradeNoisyForbiddenFilterTests(TestCase):
    """Cover the level-downgrade logic on the request logger filter."""

    @override
    def setUp(self) -> None:
        """Build one filter shared across the cases."""
        self.flt = DowngradeNoisyForbiddenFilter(_FILTER_NAME)  # pyright: ignore[reportUninitializedInstanceVariable]

    def test_downgrades_noisy_path(self) -> None:
        """First-load profile probe becomes DEBUG."""
        record = _build_record(
            logging.WARNING, "%s: %s", "Forbidden", "/api/v3/auth/profile/"
        )
        kept = self.flt.filter(record)
        assert kept is True
        assert record.levelno == logging.DEBUG
        assert record.levelname == "DEBUG"

    def test_keeps_unrelated_forbidden_at_warning(self) -> None:
        """A Forbidden on a non-noisy path stays at WARNING."""
        record = _build_record(
            logging.WARNING, "%s: %s", "Forbidden", "/api/v3/admin/users/"
        )
        kept = self.flt.filter(record)
        assert kept is True
        assert record.levelno == logging.WARNING

    def test_keeps_non_forbidden_at_warning(self) -> None:
        """A Bad Request line through django.request stays at WARNING."""
        record = _build_record(
            logging.WARNING, "%s: %s", "Bad Request", "/api/v3/auth/profile/"
        )
        kept = self.flt.filter(record)
        assert kept is True
        assert record.levelno == logging.WARNING

    def test_ignores_non_warning_levels(self) -> None:
        """ERROR-level records pass through untouched."""
        record = _build_record(
            logging.ERROR, "%s: %s", "Forbidden", "/api/v3/auth/profile/"
        )
        kept = self.flt.filter(record)
        assert kept is True
        assert record.levelno == logging.ERROR
