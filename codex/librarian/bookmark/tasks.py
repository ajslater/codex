"""Bookmark Tasks."""

from abc import ABC
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class BookmarkTask(ABC):  # noqa: B024
    """Bookmark Base Class."""


@dataclass
class BookmarkUpdateTask(BookmarkTask):
    """Bookmark a page."""

    auth_filter: Mapping[str, int | str | None]
    comic_pks: tuple[int]
    updates: Mapping[str, Any]


@dataclass
class UserActiveTask(BookmarkTask):
    """Update the user's last active status."""

    pk: int


class ClearLibrarianStatusTask(BookmarkTask):
    """Clear all librarian statuses."""


@dataclass
class CodexLatestVersionTask(BookmarkTask):
    """Get the latest version."""

    force: bool = False
