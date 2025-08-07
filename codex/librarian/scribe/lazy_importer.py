"""Kick off an import task for one batch of books."""

from codex.choices.admin import AdminFlagChoices
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.worker import WorkerBase
from codex.models.admin import AdminFlag
from codex.models.comic import Comic


class LazyImporter(WorkerBase):
    """Kick off an import task for just these books."""

    def lazy_import(self, task):
        """Kick off an import task for just these books."""
        if not AdminFlag.objects.get(
            key=AdminFlagChoices.LAZY_IMPORT_METADATA.value
        ).on:
            self.log.debug("Lazy Import disabled by flag.")
            return

        if task.group == "c":
            comics = Comic.objects.filter(pk__in=task.pks).only("path", "library_id")
        elif task.group == "f":
            comics = Comic.objects.filter(parent_folder__in=task.pks).only(
                "path", "library_id"
            )
        else:
            self.log.warning(f"No lazy import enabled for group {task}")
            return

        # Map comics to libraries.
        library_path_map = {}
        for comic in comics:
            library_id = comic.library_id  # pyright: ignore[reportAttributeAccessIssue]
            if library_id not in library_path_map:
                library_path_map[library_id] = set()
            library_path_map[library_id].add(comic.path)

        for library_id, paths in library_path_map.items():
            # An abridged import task.
            if files_modified := frozenset(paths):
                task = ImportTask(
                    library_id=library_id,
                    files_modified=files_modified,
                    force_import_metadata=True,
                )
                self.librarian_queue.put(task)
