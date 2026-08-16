"""Bookmark Tasks."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from codex.librarian.tasks import LibrarianTask


class BookmarkTask(LibrarianTask):
    """Bookmark Base Class."""


@dataclass
class BookmarkUpdateTask(BookmarkTask):
    """Bookmark a page."""

    auth_filter: Mapping[str, int | str | None]
    comic_pks: tuple[int, ...]
    updates: Mapping[str, Any]


@dataclass
class LastRouteUpdateTask(BookmarkTask):
    """
    Persist a browser's last route off the request thread.

    Browse GETs fire one of these instead of writing the
    SettingsBrowserLastRoute row synchronously — the read path must
    never wait on the WAL writer lock (a navigation measured 1.85s vs
    12ms under a concurrent librarian write transaction). The
    aggregator keys on ``settings_pk`` so rapid navigation collapses
    to one write per flood window.
    """

    settings_pk: int
    route: Mapping[str, Any]


@dataclass
class UserActiveTask(BookmarkTask):
    """Update the user's last active status."""

    pk: int


class ClearLibrarianStatusTask(BookmarkTask):
    """Clear all librarian statuses."""


@dataclass
class CodexLatestVersionTask(BookmarkTask):
    """
    Get the latest version.

    ``update`` requests that a successful fetch chain into a
    ``JanitorCodexUpdateTask`` if the Auto Update admin flag is on.
    Only the nightly janitor sets it. Chaining (rather than queueing
    both tasks up front) keeps the update from racing ahead of the
    fetch that tells it whether an update is even available.
    """

    force: bool = False
    update: bool = False
