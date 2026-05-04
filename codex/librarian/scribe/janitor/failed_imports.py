"""Force update events for failed imports."""

from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.janitor.vacuum import JanitorVacuum
from codex.models import FailedImport, Library


class JanitorUpdateFailedImports(JanitorVacuum):
    """Methods for updating failed imports."""

    def _force_update_failed_imports(self, library_id) -> None:
        """Force update events for failed imports in a library."""
        failed_import_paths = frozenset(
            FailedImport.objects.filter(library=library_id).values_list(
                "path", flat=True
            )
        )
        if not failed_import_paths:
            return
        task = ImportTask(
            library_id=library_id,
            files_modified=failed_import_paths,
        )
        self.librarian_queue.put(task)

    def force_update_all_failed_imports(self) -> None:
        """Force update events for failed imports in every library."""
        pks = Library.objects.filter(covers_only=False).values_list("pk", flat=True)
        for pk in pks:
            self._force_update_failed_imports(pk)
