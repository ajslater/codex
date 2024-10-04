"""Bulk import and move comics and folders."""

from pathlib import Path

from django.utils import timezone

from codex.librarian.importer.importer import ComicImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.importer.tasks import (
    AdoptOrphanFoldersTask,
    ImportDBDiffTask,
    LazyImportComicsTask,
    UpdateGroupsTask,
)
from codex.librarian.janitor.tasks import JanitorAdoptOrphanFoldersFinishedTask
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.models import Comic, Folder, Library
from codex.status import Status
from codex.threads import QueuedThread


class ComicImporterThread(QueuedThread):
    """A worker to handle all bulk database updates."""

    def _create_importer(self, task):
        return ComicImporter(task, self.log_queue, self.librarian_queue)

    def _import(self, task):
        """Run an import task."""
        importer = self._create_importer(task)
        importer.apply()

    def _lazy_import_metadata(self, task):
        """Kick off an import task for just these books."""
        import_comics = Comic.objects.filter(pk__in=task.pks).only("path", "library_id")
        library_path_map = {}
        for import_comic in import_comics:
            library_id = import_comic.library_id  # type: ignore
            if library_id not in library_path_map:
                library_path_map[library_id] = set()
            library_path_map[library_id].add(import_comic.path)

        for library_id, paths in library_path_map.items():
            # An abridged import task.
            task = ImportDBDiffTask(
                library_id=library_id,
                files_modified=frozenset(paths),
                force_import_metadata=True,
            )
            self._import(task)

    def _update_groups(self, task):
        pks = Library.objects.filter(covers_only=False).values_list("pk", flat=True)
        start_time = task.start_time if task.start_time else timezone.now()
        for pk in pks:
            task = ImportDBDiffTask(library_id=pk)
            importer = self._create_importer(task)
            importer.update_all_groups({}, start_time)
        self.librarian_queue.put(LIBRARY_CHANGED_TASK)

    def _adopt_orphan_folders_for_library(self, library):
        """Adopt orphan folders for one library."""
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
            return False

        # An abridged import task.
        task = ImportDBDiffTask(
            library_id=library.pk,
            dirs_moved=folders_moved,
        )
        importer = self._create_importer(task)
        # Only run the moved task.
        importer.bulk_folders_moved()
        return True

    def _adopt_orphan_folders(self, janitor=False):
        """Find orphan folders and move them into their correct place."""
        status = Status(ImportStatusTypes.ADOPT_FOLDERS)
        moved_status = Status(ImportStatusTypes.DIRS_MOVED)
        try:
            self.status_controller.start(status)
            self.status_controller.start(moved_status)
            libraries = Library.objects.filter(covers_only=False).only("path")
            for library in libraries.iterator():
                folders_left = True
                while folders_left:
                    # Run until there are no orphan folders
                    folders_left = self._adopt_orphan_folders_for_library(library)
        finally:
            self.status_controller.finish_many((moved_status, status))
            if janitor:
                next_task = JanitorAdoptOrphanFoldersFinishedTask()
                self.librarian_queue.put(next_task)

    def process_item(self, item):
        """Run the updater."""
        task = item
        if isinstance(task, ImportDBDiffTask):
            self._import(task)
        elif isinstance(task, LazyImportComicsTask):
            self._lazy_import_metadata(task)
        elif isinstance(task, UpdateGroupsTask):
            self._update_groups(task)
        elif isinstance(task, AdoptOrphanFoldersTask):
            self._adopt_orphan_folders(task.janitor)
        else:
            self.log.warning(f"Bad task sent to library updater {task}")
