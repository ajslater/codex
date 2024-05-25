"""Force update events for failed imports."""

from watchdog.events import FileModifiedEvent

from codex.librarian.watchdog.tasks import WatchdogEventTask
from codex.models import FailedImport, Library
from codex.worker_base import WorkerBaseMixin


class UpdateFailedImportsMixin(WorkerBaseMixin):
    """Methods for updating failed imports."""

    def _force_update_failed_imports(self, library_id):
        """Force update events for failed imports in a library."""
        failed_import_paths = FailedImport.objects.filter(
            library=library_id
        ).values_list("path", flat=True)
        for path in failed_import_paths:
            event = FileModifiedEvent(path)
            task = WatchdogEventTask(library_id, event)
            self.librarian_queue.put(task)

    def force_update_all_failed_imports(self):
        """Force update events for failed imports in every library."""
        pks = Library.objects.filter(covers_only=False).values_list("pk", flat=True)
        for pk in pks:
            self._force_update_failed_imports(pk)
