"""Kick off an import task for one batch of books."""

from multiprocessing import Queue

from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.worker import WorkerMixin
from codex.models.comic import Comic


class LazyImporter(WorkerMixin):
    """Kick off an import task for just these books."""

    def lazy_import(self, task):
        """Kick off an import task for just these books."""
        comics = Comic.objects.filter(pk__in=task.pks).only("path", "library_id")
        # Map comics to libraries.
        library_path_map = {}
        for comic in comics:
            library_id = comic.library_id  # pyright: ignore[reportAttributeAccessIssue]
            if library_id not in library_path_map:
                library_path_map[library_id] = set()
            library_path_map[library_id].add(comic.path)

        for library_id, paths in library_path_map.items():
            # An abridged import task.
            task = ImportTask(
                library_id=library_id,
                files_modified=frozenset(paths),
                force_import_metadata=True,
            )
            self.librarian_queue.put(task)

    def __init__(self, logger_, librarian_queue: Queue):
        """Initialize Worker."""
        self.init_worker(logger_, librarian_queue)
