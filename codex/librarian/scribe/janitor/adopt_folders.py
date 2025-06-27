"""Bulk import and move comics and folders."""

from multiprocessing import Queue
from pathlib import Path

from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.status import ImporterStatusTypes
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.janitor.status import JanitorStatusTypes
from codex.librarian.scribe.search.tasks import SearchIndexUpdateTask
from codex.librarian.status import Status
from codex.librarian.worker import WorkerStatusMixin
from codex.models import Folder, Library


class OrphanFolderAdopter(WorkerStatusMixin):
    """A worker to handle all bulk database updates."""

    def _adopt_orphan_folders_for_library(self, library):
        """Adopt orphan folders for one library."""
        count = 0
        orphan_folder_paths = (
            Folder.objects.filter(library=library, parent_folder=None)
            .exclude(path=library.path)
            .values_list("path", flat=True)
        )
        # Move in place
        # Exclude deleted folders
        folders_moved = {
            path: path for path in orphan_folder_paths if Path(path).is_dir()
        }

        if folders_moved:
            self.log.debug(
                f"{len(folders_moved)} orphan folders found in {library.path}"
            )
        else:
            self.log.debug(f"No orphan folders in {library.path}")
            return False, count

        # An abridged import task.
        task = ImportTask(library_id=library.pk, dirs_moved=folders_moved)
        importer = ComicImporter(task, self.log, self.librarian_queue, self.abort_event)
        count = importer.bulk_folders_moved(mark_in_progress=True)
        return True, count

    def adopt_orphan_folders(self):
        """Find orphan folders and move them into their correct place."""
        self.abort_event.clear()
        status = Status(JanitorStatusTypes.ADOPT_ORPHAN_FOLDERS)
        moved_status = Status(ImporterStatusTypes.MOVE_FOLDERS)
        total_count = 0
        try:
            self.status_controller.start_many((status, moved_status))
            libraries = Library.objects.filter(covers_only=False).only("path")
            for library in libraries.iterator():
                folders_left = True
                while folders_left:
                    if self.abort_event.is_set():
                        return
                    # Run until there are no orphan folders
                    folders_left, count = self._adopt_orphan_folders_for_library(
                        library
                    )
                    total_count += count
        finally:
            self.status_controller.finish_many((moved_status, status))
            if total_count:
                self.librarian_queue.put(LIBRARY_CHANGED_TASK)
                task = SearchIndexUpdateTask()
                self.librarian_queue.put(task)
            if self.abort_event.is_set():
                self.log.debug("Adopt Orphan Folders aborted early.")

            self.abort_event.clear()

    def __init__(self, logger_, librarian_queue: Queue, event):
        """Initialize Worker."""
        self.abort_event = event
        self.init_worker(logger_, librarian_queue)
