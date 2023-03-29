"""Clean up the database after moves or imports."""

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.models import Comic, Folder
from codex.threads import QueuedThread


class DeletedMixin(QueuedThread):
    """Clean up database methods."""

    def _remove_covers(self, delete_comic_pks):
        task = CoverRemoveTask(delete_comic_pks)
        self.librarian_queue.put(task)

    @status_notify(status_type=ImportStatusTypes.DIRS_DELETED, updates=False)
    def bulk_folders_deleted(self, delete_folder_paths, library, **kwargs):
        """Bulk delete folders."""
        if not delete_folder_paths:
            return 0
        folders = Folder.objects.filter(library=library, path__in=delete_folder_paths)
        delete_comic_pks = frozenset(
            Comic.objects.filter(library=library, folders__in=folders)
            .distinct()
            .values_list("pk", flat=True)
        )
        folders.delete()

        self._remove_covers(delete_comic_pks)

        count = len(delete_folder_paths)
        self.log.info(
            f"Deleted {count} folders and {len(delete_comic_pks)} comics"
            f"from {library.path}"
        )
        return count

    @status_notify(status_type=ImportStatusTypes.FILES_DELETED, updates=False)
    def bulk_comics_deleted(self, delete_comic_paths, library, **kwargs):
        """Bulk delete comics found missing from the filesystem."""
        if not delete_comic_paths:
            return 0
        comics = Comic.objects.filter(library=library, path__in=delete_comic_paths)
        delete_comic_pks = frozenset(comics.values_list("pk", flat=True))
        comics.delete()

        self._remove_covers(delete_comic_pks)

        count = len(delete_comic_paths)
        self.log.info(f"Deleted {count} comics from {library.path}")

        return count
