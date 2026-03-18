"""Poller Tasks."""

from dataclasses import dataclass

from codex.librarian.fs.tasks import FSTask


@dataclass
class FSPollLibrariesTask(FSTask):
    """Tell poller to poll these libraries now."""

    library_ids: frozenset
    force: bool
