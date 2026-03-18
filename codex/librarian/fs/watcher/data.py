"""Dataclass for events post processing changes."""

from dataclasses import dataclass, field

from codex.librarian.fs.events import FSEvent


@dataclass
class ChangeBatch:
    """Accumulated changes from a single watchfiles batch."""

    # (library_pk, FSEvent) pairs, grouped by change type
    added: list[tuple[int, FSEvent]] = field(default_factory=list)
    deleted: list[tuple[int, FSEvent]] = field(default_factory=list)
    modified: list[tuple[int, FSEvent]] = field(default_factory=list)
    # Dir deletes expanded from DB, kept separate so they bypass move matching
    dir_deleted: list[tuple[int, FSEvent]] = field(default_factory=list)
