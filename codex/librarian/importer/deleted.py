"""Clean up the database after moves or imports."""
import logging

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.models import Comic, Folder
from codex.threads import QueuedThread


class DeletedMixin(QueuedThread):
    """Clean up database methods."""

    def bulk_folders_deleted(self, library, delete_folder_paths, count, _total):
        """Bulk delete folders."""
        if not delete_folder_paths:
            return False
        query = Folder.objects.filter(library=library, path__in=delete_folder_paths)
        (num_del, _) = query.delete()
        count += num_del
        if count:
            level = logging.INFO
        else:
            level = logging.DEBUG
        self.log.log(level, f"Deleted {count} folders from {library.path}")
        return count

    def bulk_comics_deleted(self, library, delete_comic_paths, count, _total):
        """Bulk delete comics found missing from the filesystem."""
        if not delete_comic_paths:
            return False
        query = Comic.objects.filter(library=library, path__in=delete_comic_paths)
        delete_comic_pks = frozenset(query.values_list("pk", flat=True))
        task = CoverRemoveTask(delete_comic_pks)
        self.librarian_queue.put(task)

        (num_del, _) = query.delete()
        count += num_del
        if count:
            level = logging.INFO
        else:
            level = logging.DEBUG
        self.log.log(level, f"Deleted {count} comics from {library.path}")
        return count
