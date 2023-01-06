"""Force update events for failed imports."""
from watchdog.events import FileModifiedEvent

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.watchdog.tasks import WatchdogEventTask
from codex.models import FailedImport, Library
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


def force_update_failed_imports(library_id):
    """Force update events for failed imports in a library."""
    failed_import_paths = FailedImport.objects.filter(library=library_id).values_list(
        "path", flat=True
    )
    for path in failed_import_paths:
        event = FileModifiedEvent(path)
        task = WatchdogEventTask(library_id, event)
        LIBRARIAN_QUEUE.put(task)


def force_update_all_failed_imports():
    """Force update events for failed imports in every library."""
    pks = Library.objects.values_list("pk", flat=True)
    for pk in pks:
        force_update_failed_imports(pk)
