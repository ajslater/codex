"""Clean up covers from the db."""

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.scribe.importer.delete.existence import confirm_deleted
from codex.librarian.scribe.importer.search import SearchIndexImporter
from codex.librarian.scribe.importer.statii.delete import ImporterRemoveCoversStatus
from codex.models.paths import CustomCover


class DeletedCoversImporter(SearchIndexImporter):
    """Clean up covers from the db."""

    def remove_covers(self, delete_pks, *, custom: bool) -> None:
        """Queue a remove covers task."""
        task = CoverRemoveTask(delete_pks, custom)
        self.librarian_queue.put(task)

    def bulk_covers_deleted(self, **kwargs) -> int:
        """Bulk delete comics found missing from the filesystem."""
        status = ImporterRemoveCoversStatus(
            0, len(self.task.covers_deleted), log_success=False
        )
        try:
            if not self.task.covers_deleted:
                return 0
            self.status_controller.start(status)
            paths = confirm_deleted(self.task.covers_deleted, self.log, "covers")
            self.task.covers_deleted = frozenset()
            if not paths:
                return 0
            covers = CustomCover.objects.filter(library=self.library, path__in=paths)
            delete_cover_pks = frozenset(covers.values_list("pk", flat=True))
            count, _ = covers.delete()

            self.remove_covers(delete_cover_pks, custom=True)
        finally:
            self.status_controller.finish(status)

        return count
