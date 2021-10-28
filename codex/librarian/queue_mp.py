"""Library Queue and task definitions."""
# THIS file cannot be named queue or it causes weird type checker errors
from dataclasses import dataclass
from multiprocessing import SimpleQueue


@dataclass
class LibraryTask:
    """Task for a particular library."""

    library_id: int


@dataclass
class ScanRootTask(LibraryTask):
    """Scan a library."""

    force: bool


@dataclass
class ComicCoverCreateTask(LibraryTask):
    """Create a comic cover."""

    src_path: str
    db_cover_path: str
    force: bool


@dataclass
class BulkMovedTask(LibraryTask):
    moved_paths: dict


@dataclass
class BulkFolderMovedTask(BulkMovedTask):
    pass


@dataclass
class BulkComicMovedTask(BulkMovedTask):
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
