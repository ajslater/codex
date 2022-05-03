"""Library SimpleQueue and task definitions."""
# This file cannot be named queue or it causes weird type checker errors
from abc import ABC
from dataclasses import dataclass
from multiprocessing import Queue

from watchdog.events import FileSystemEvent


@dataclass
class LibraryTask(ABC):
    """Task for a particular library."""

    library_id: int


@dataclass
class WatchdogEventTask(LibraryTask):
    """Task for filesystem events."""

    event: FileSystemEvent


@dataclass
class UpdaterTask(ABC):
    """Tasks for the updater."""

    pass


@dataclass
class DBDiffTask(UpdaterTask, LibraryTask):
    """For sending to the updater."""

    dirs_moved: dict
    files_moved: dict
    dirs_modified: frozenset
    files_modified: frozenset
    # dirs_created: set
    files_created: frozenset
    dirs_deleted: frozenset
    files_deleted: frozenset


@dataclass
class ComicCoverTask(ABC):
    """Handle with the CoverCreator."""

    pass


@dataclass
class ImageComicCoverCreateTask(ComicCoverTask):
    """A comic cover with image data."""

    force: bool
    comic_path: str
    cover_image_data: bytes


@dataclass
class BulkComicCoverCreateTask(ComicCoverTask):
    """A list of comic src and dest paths."""

    force: bool
    comics: tuple


@dataclass
class CreateMissingCoversTask(ComicCoverTask):
    """Create covers for comics without them."""

    pass


@dataclass
class CleanupMissingComicCovers(ComicCoverTask):
    """Clean up covers from missing comics."""

    pass


@dataclass
class LibrariesTask(ABC):
    """Tasks over a set of libraries."""

    library_ids: frozenset


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

    cover_paths: frozenset


@dataclass
class PollLibrariesTask(LibrariesTask):
    """Tell observer to poll these libraries now."""

    force: bool


@dataclass
class WatchdogSyncTask:
    """Sync watches with libraries."""

    pass


@dataclass
class NotifierTask(ABC):
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
class JanitorTask(ABC):
    """Tasks for the janitor."""

    pass


@dataclass
class BackupTask(JanitorTask):
    """Backup the database."""

    pass


@dataclass
class RestartTask:
    """for restart."""

    pass


@dataclass
class UpdateTask(JanitorTask):
    """Task for updater."""

    force: bool


@dataclass
class VacuumTask(JanitorTask):
    """Vacuum the database."""

    pass


@dataclass
class CleanSearchTask(JanitorTask):
    """Clean the search db."""

    pass


@dataclass
class CleanFKsTask(JanitorTask):
    """Clean unused foreign keys."""

    pass


@dataclass
class SearchIndexerTask(ABC):
    """Tasks for the search indexer."""

    pass


@dataclass
class SearchIndexRebuildIfDBChangedTask(SearchIndexerTask):
    """Task to check if the db is changed and schedule an update task."""

    pass


@dataclass
class SearchIndexUpdateTask(SearchIndexerTask):
    """Update the search index."""

    rebuild: bool


@dataclass
class DelayedTasks:
    """A list of tasks to start on a delay."""

    delay: int
    tasks: tuple


LIBRARIAN_QUEUE = Queue()
