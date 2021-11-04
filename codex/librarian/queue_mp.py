"""Library SimpleQueue and task definitions."""
# This file cannot be named queue or it causes weird type checker errors
from dataclasses import dataclass
from multiprocessing import Queue


@dataclass
class LibraryTask:
    """Task for a particular library."""

    library_id: int


@dataclass
class ScannerTask:
    pass


@dataclass
class ScanRootTask(LibraryTask, ScannerTask):
    """Scan a library."""

    force: bool


@dataclass
class BulkMovedTask(LibraryTask, ScannerTask):
    """Move Folders or Comics."""

    moved_paths: dict


@dataclass
class BulkFolderMovedTask(BulkMovedTask):
    """Move Folders."""

    pass


@dataclass
class BulkComicMovedTask(BulkMovedTask):
    """Move Comics."""

    pass


@dataclass
class ComicCoverCreateTask:
    force: bool


@dataclass
class SingleComicCoverCreateTask(ComicCoverCreateTask):
    comic: dict


@dataclass
class BulkComicCoverCreateTask(ComicCoverCreateTask):
    comics: tuple


@dataclass
class SleepTask:
    """A task that must sleep a tiny bit for db consistency."""

    sleep: int


@dataclass
class WatcherCronTask(SleepTask):
    """Cron for watcherd."""

    pass


@dataclass
class ScannerCronTask(SleepTask, ScannerTask):
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
class NotifierTask:
    text: str


@dataclass
class AdminNotifierTask(NotifierTask):
    """Notifications for finished scans."""

    pass


@dataclass
class BroadcastNotifierTask(NotifierTask):
    pass


@dataclass
class VacuumCronTask:
    """Vaccum the database."""

    pass


LIBRARIAN_QUEUE = Queue()
