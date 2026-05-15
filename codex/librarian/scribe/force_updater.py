"""Force a metadata re-import for an explicit set of comic pks."""

from collections import defaultdict

from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.tasks import ForceUpdateComicsTask
from codex.librarian.worker import WorkerBase
from codex.models.comic import Comic


class ForceUpdater(WorkerBase):
    """Dispatch ImportTasks scoped to a caller-supplied set of comic pks."""

    def force_update(self, task: ForceUpdateComicsTask) -> None:
        """Group comic pks by library and dispatch a forced ImportTask per library."""
        if not task.comic_pks:
            self.log.debug("Force update called with no comic pks.")
            return

        comics = Comic.objects.filter(pk__in=task.comic_pks).only("path", "library_id")
        library_path_map: defaultdict[int, set[str]] = defaultdict(set)
        for comic in comics:
            library_path_map[comic.library_id].add(comic.path)  # pyright: ignore[reportAttributeAccessIssue]

        total = 0
        for library_id, paths in library_path_map.items():
            files_modified = frozenset(paths)
            if not files_modified:
                continue
            import_task = ImportTask(
                library_id=library_id,
                files_modified=files_modified,
                force_import_metadata=True,
                check_metadata_mtime=False,
            )
            self.librarian_queue.put(import_task)
            total += len(files_modified)
        self.log.info(f"Force update queued for {total} comics.")
