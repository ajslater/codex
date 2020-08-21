"""Library Queue and task definitions."""
from dataclasses import dataclass
from multiprocessing import Queue


@dataclass
class ScanRootTask:
    """Scan a Root Path."""

    root_path_id: int
    force: bool


@dataclass
class ComicTask:
    """Base class for comic tasks."""

    src_path: str


@dataclass
class ComicModifiedTask(ComicTask):
    """Created and Modified comics share the same task."""

    root_path_id: int
    pass


@dataclass
class ComicMovedTask(ComicTask):
    """Moved comic task."""

    dest_path: str


@dataclass
class ComicDeletedTask(ComicTask):
    """Deleted comic."""

    pass


@dataclass
class FolderMovedTask(ComicTask):
    """Moved comic task."""

    dest_path: str


@dataclass
class FolderDeletedTask(ComicTask):
    """Deleted comic."""

    pass


QUEUE = Queue()
