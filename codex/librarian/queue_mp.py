"""Library Queue and task definitions."""
# THIS file cannot be named queue or it causes weird type checker errors
from dataclasses import dataclass
from multiprocessing import SimpleQueue


@dataclass
class ScanRootTask:
    """Scan a library."""

    library_id: int
    force: bool


@dataclass
class ComicTask:
    """Base class for comic tasks."""

    library_id: int
    src_path: str


@dataclass
class ComicModifiedTask(ComicTask):
    """Created and Modified comics share the same task."""

    pass


@dataclass
class ComicCreatedTask(ComicTask):
    """Created and Modified comics share the same task."""

    pass


@dataclass
class ComicCoverCreateTask(ComicTask):
    """Create a comic cover."""

    db_cover_path: str
    force: bool


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


@dataclass
class SleepTask:
    """A task that must sleep a tiny bit for db consistency."""

    sleep: int


@dataclass
class LibraryChangedTask:
    """Library Changed."""

    pass


@dataclass
class WatcherCronTask(SleepTask):
    """Cron for watcherd."""

    pass


@dataclass
class ScannerCronTask(SleepTask):
    """Cron for scanner."""

    pass


@dataclass
class UpdateCronTask(SleepTask):
    """Task for updater."""

    force: bool


@dataclass
class RestartTask(SleepTask):
    """for restart."""

    pass


@dataclass
class ScanDoneTask(SleepTask):
    """Notifications for finished scans."""

    failed_imports: bool


@dataclass
class VacuumCronTask:
    """Vaccum the database."""

    pass


QUEUE = SimpleQueue()
