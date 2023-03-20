"""Clean up the database after moves or imports."""

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.importer.status import ImportStatusTypes, status
from codex.models import Comic, Folder
from codex.threads import QueuedThread


class DeletedMixin(QueuedThread):
    """Clean up database methods."""

    @status(status=ImportStatusTypes.DIRS_DELETED, updates=False)
    def bulk_folders_deleted(self, delete_folder_paths, library, status_args=None):
        """Bulk delete folders."""
        if not delete_folder_paths:
            return 0
        query = Folder.objects.filter(library=library, path__in=delete_folder_paths)
        query.delete()
        count = len(delete_folder_paths)
        self.log.info(f"Deleted {count} folders from {library.path}")
        return count

    @status(status=ImportStatusTypes.FILES_DELETED, updates=False)
    def bulk_comics_deleted(self, delete_comic_paths, library, status_args=None):
        """Bulk delete comics found missing from the filesystem."""
        if not delete_comic_paths:
            return 0
        query = Comic.objects.filter(library=library, path__in=delete_comic_paths)
        delete_comic_pks = frozenset(query.values_list("pk", flat=True))
        task = CoverRemoveTask(delete_comic_pks)
        self.librarian_queue.put(task)

        query.delete()
        count = len(delete_comic_paths)
        self.log.info(f"Deleted {count} comics from {library.path}")
        return count
