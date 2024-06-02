"""Bulk import and move comics and folders."""

from codex.librarian.importer.importer import ComicImporter
from codex.librarian.importer.tasks import (
    AdoptOrphanFoldersTask,
    ImportDBDiffTask,
    LazyImportComicsTask,
)
from codex.models import Comic, Folder, Library
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

    def _adopt_orphan_folders(self):
        """Find orphan folders and move them into their correct place."""
        libraries = Library.objects.filter(covers_only=False).only("path")
        for library in libraries.iterator():
            while True:
                # Run until there are no orphan folders
                orphan_folder_paths = (
                    Folder.objects.filter(library=library, parent_folder=None)
                    .exclude(path=library.path)
                    .values_list("path", flat=True)
                )
                if not orphan_folder_paths:
                    self.log.debug(f"No orphan folders in {library.path}")
                    break

                self.log.debug(
                    f"{len(orphan_folder_paths)} orphan folders found in {library.path}"
                )

                # Move in place
                folders_moved = {path: path for path in orphan_folder_paths}

                # An abridged import task.
                task = ImportDBDiffTask(
                    library_id=library.pk,
                    dirs_moved=folders_moved,
                )
                importer = self._create_importer(task)
                # Only run the moved task.
                importer.bulk_folders_moved()

    def process_item(self, item):
        """Run the updater."""
        task = item
        if isinstance(task, ImportDBDiffTask):
            self._import(task)
        elif isinstance(task, LazyImportComicsTask):
            self._lazy_import_metadata(task)
        elif isinstance(task, AdoptOrphanFoldersTask):
            self._adopt_orphan_folders()
        else:
            self.log.warning(f"Bad task sent to library updater {task}")
