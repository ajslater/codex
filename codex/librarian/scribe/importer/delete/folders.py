"""Delete database folders methods."""

from codex.librarian.scribe.importer.delete.comics import DeletedComicsImporter
from codex.librarian.scribe.importer.statii.delete import ImporterRemoveFoldersStatus
from codex.models.comic import Comic
from codex.models.groups import Folder


class DeletedFoldersImporter(DeletedComicsImporter):
    """Delete database folders methods."""

    def bulk_folders_deleted(self, **kwargs):
        """Bulk delete folders."""
        status = ImporterRemoveFoldersStatus(0, len(self.task.dirs_deleted))
        try:
            if not self.task.dirs_deleted:
                return 0
            self.status_controller.start(status)
            folders = Folder.objects.filter(
                library=self.library, path__in=self.task.dirs_deleted
            )
            self.task.dirs_deleted = frozenset()
            delete_comic_pks = frozenset(
                Comic.objects.filter(library=self.library, folders__in=folders)
                .distinct()
                .values_list("pk", flat=True)
            )
            folders.delete()
            count = len(delete_comic_pks)

            self.remove_covers(delete_comic_pks, custom=False)
        finally:
            self.status_controller.finish(status)
        return count
