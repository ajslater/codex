"""Library SimpleQueue and task definitions."""
# This file cannot be named queue or it causes weird type checker errors
from dataclasses import dataclass
from multiprocessing import Queue


@dataclass
class LibraryTask:
    """Task for a particular library."""

    library_id: int


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
class ComicCoverCreateTask:
    """Handle with the CoverCreator."""

    force: bool


@dataclass
class ImageComicCoverCreateTask(ComicCoverCreateTask):
    """A comic cover with image data."""

    comic_path: str
    cover_path: str
    image_data: bytes


@dataclass
class BulkComicCoverCreateTask(ComicCoverCreateTask):
    """A list of comic src and dest paths."""

    comics: tuple


@dataclass
class PollLibrariesTask:
    """Tell observer to poll these libraries now."""

    library_ids: set
    force: bool


@dataclass
class SleepTask:
    """A task that must sleep a tiny bit for db consistency."""

    sleep: int


@dataclass
class WatchdogTask:
    """Sync watches with libraries."""

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
    """Vaccum the database."""

    pass


LIBRARIAN_QUEUE = Queue()
