"""DB Updater Tasks."""
from dataclasses import dataclass


@dataclass
class UpdaterTask:
    """Tasks for the updater."""

    pass


@dataclass
class UpdaterDBDiffTask(UpdaterTask):
    """For sending to the updater."""

    library_id: int
    dirs_moved: dict
    files_moved: dict
    dirs_modified: frozenset
    files_modified: frozenset
    # dirs_created
    files_created: frozenset
    dirs_deleted: frozenset
    files_deleted: frozenset
