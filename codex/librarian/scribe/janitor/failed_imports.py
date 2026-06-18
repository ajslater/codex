"""Force update events for failed imports."""

from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.janitor.vacuum import JanitorVacuum
from codex.models import FailedImport, Library


class JanitorUpdateFailedImports(JanitorVacuum):
    """Methods for updating failed imports."""

    def _force_update_failed_imports(self, library_id) -> int:
        """Queue a forced re-import of a library's failed imports; return the count."""
        failed_import_paths = frozenset(
            FailedImport.objects.filter(library=library_id).values_list(
                "path", flat=True
            )
        )
        if not failed_import_paths:
            return 0
        task = ImportTask(
            library_id=library_id,
            files_modified=failed_import_paths,
        )
        self.librarian_queue.put(task)
        return len(failed_import_paths)

    def force_update_all_failed_imports(self) -> None:
        """Force update events for failed imports in every library and log the total."""
        pks = Library.objects.values_list("pk", flat=True)
        total = 0
        for pk in pks:
            total += self._force_update_failed_imports(pk)
        self.log.info(f"Force update queued for {total} failed imports.")
