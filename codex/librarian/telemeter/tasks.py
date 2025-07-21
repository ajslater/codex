"""Telemter tasks."""

from dataclasses import dataclass

from codex.librarian.bookmark.tasks import BookmarkTask


@dataclass
class TelemeterTask(BookmarkTask):
    """Send telemetry."""
