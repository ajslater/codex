"""Library SimpleQueue and task definitions."""
# This file cannot be named queue or it causes weird type checker errors
from dataclasses import dataclass
from multiprocessing import Queue

from watchdog.events import FileSystemEvent


@dataclass
class LibraryTask:
    """Task for a particular library."""

    library_id: int


@dataclass
class WatchdogEventTask(LibraryTask):
    """Task for filesystem events."""

    event: FileSystemEvent


@dataclass
class DBDiffTask(LibraryTask):
    """For sending to the updater."""

    dirs_moved: dict
    files_moved: dict
    dirs_modified: set
    files_modified: set
    # dirs_created: set
    files_created: set
    dirs_deleted: set
    files_deleted: set


@dataclass
class ComicCoverTask:
    """Handle with the CoverCreator."""


@dataclass
class ImageComicCoverCreateTask(ComicCoverTask):
    """A comic cover with image data."""

    force: bool
    comic_path: str
    cover_path: str
    image_data: bytes


@dataclass
class BulkComicCoverCreateTask(ComicCoverTask):
    """A list of comic src and dest paths."""

    force: bool
    comics: tuple


@dataclass
class LibrariesTask:
    """Tasks over a set of libraries."""

    library_ids: set


@dataclass
class CreateComicCoversLibrariesTask(ComicCoverTask, LibrariesTask):
    """Create Comic covers for a set of libraries."""

    pass


@dataclass
class PurgeComicCoversLibrariesTask(ComicCoverTask, LibrariesTask):
    """Purge all covers for a set of libraries."""

    pass


@dataclass
class PurgeComicCoversTask(ComicCoverTask):
    """Purge a set of comic cover_paths."""

    cover_paths: set


@dataclass
class PollLibrariesTask(LibrariesTask):
    """Tell observer to poll these libraries now."""

    force: bool


@dataclass
class WatchdogSyncTask:
    """Sync watches with libraries."""

    pass


@dataclass
class UpdateCronTask:
    """Task for updater."""

    force: bool


@dataclass
class RestartTask:
    """for restart."""

    pass


@dataclass
class NotifierTask:
    """Handle with the Notifier."""

    text: str


@dataclass
class AdminNotifierTask(NotifierTask):
    """Notifications for admins only."""

    pass


@dataclass
class BroadcastNotifierTask(NotifierTask):
    """Notifications for all users."""

    pass


@dataclass
class VacuumCronTask:
    """Vacuum the database."""

    pass


@dataclass
class BackupCronTask:
    """Backup the database."""

    pass


LIBRARIAN_QUEUE = Queue()
