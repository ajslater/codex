"""Unit test for the shared fts_rebuild() success log."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.test import TestCase
from loguru import logger

from codex.librarian.scribe.janitor.integrity import fts_rebuild

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def _capture_logs() -> Generator[list[str]]:
    """Collect loguru INFO+ messages emitted inside the ``with`` block."""
    records: list[str] = []
    sink_id = logger.add(records.append, level="INFO", format="{message}")
    try:
        yield records
    finally:
        logger.remove(sink_id)


class FtsRebuildTests(TestCase):
    """The shared rebuild helper logs its own success, like its integrity siblings."""

    def test_fts_rebuild_logs_success(self) -> None:
        """Any caller of the shared fn gets a completion log, not just the wrapper."""
        with _capture_logs() as logs:
            fts_rebuild(logger)
        assert any("Rebuilt the Full Text Search Index" in line for line in logs)
