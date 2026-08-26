"""Delete database folders methods."""

from codex.librarian.scribe.importer.delete.comics import DeletedComicsImporter
from codex.librarian.scribe.importer.delete.existence import confirm_deleted
from codex.librarian.scribe.importer.statii.delete import ImporterRemoveFoldersStatus
from codex.models.collections import Folder
from codex.models.comic import Comic


class DeletedFoldersImporter(DeletedComicsImporter):
    """Delete database folders methods."""

    def bulk_folders_deleted(self, **kwargs) -> tuple[int, int, dict]:
        """
        Bulk delete folders. Return (folders, cascaded comics, collections).

        Comics under a deleted folder die by the ``parent_folder`` cascade
        rather than through ``bulk_comics_deleted``, so their collections
        are gathered here too. Without them a series or publisher emptied by
        a folder delete is never re-stamped, and browsers viewing it keep
        listing comics that are gone until some unrelated import moves the
        timestamp.
        """
        status = ImporterRemoveFoldersStatus(0, len(self.task.dirs_deleted))
        deleted_comic_collections = self._init_deleted_comic_collections()
        try:
            if not self.task.dirs_deleted:
                return 0, 0, deleted_comic_collections
            self.status_controller.start(status)
            paths = confirm_deleted(self.task.dirs_deleted, self.log, "folders")
            self.task.dirs_deleted = frozenset()
            if not paths:
                return 0, 0, deleted_comic_collections
            folders = Folder.objects.filter(library=self.library, path__in=paths)
            folder_count = folders.count()
            delete_comic_qs = Comic.objects.filter(
                library=self.library, folders__in=folders
            ).distinct()
            self._populate_deleted_comic_collections(
                delete_comic_qs, deleted_comic_collections
            )
            delete_comic_pks = frozenset(delete_comic_qs.values_list("pk", flat=True))
            folders.delete()

            self.remove_covers(delete_comic_pks, custom=False)
        finally:
            self.status_controller.finish(status)
        return folder_count, len(delete_comic_pks), deleted_comic_collections
