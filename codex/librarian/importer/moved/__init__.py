"""Bulk import and move comics and folders."""

from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.importer.const import BULK_UPDATE_FOLDER_MODIFIED_FIELDS
from codex.librarian.importer.moved.folders import MovedFoldersImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.status import Status
from codex.models import Folder


class MovedImporter(MovedFoldersImporter):
    """Methods for moving comics and folders."""

    def _bulk_folders_modified(self):
        """Update folders stat and nothing else."""
        num_dirs_modified = len(self.task.dirs_modified)
        if not num_dirs_modified:
            return
        status = Status(ImportStatusTypes.UPDATE_FOLDERS, None, num_dirs_modified)
        self.status_controller.start(status)

        folders = Folder.objects.filter(
            library=self.library, path__in=self.task.dirs_modified
        ).only("stat", "updated_at")
        self.task.dirs_modified = frozenset()
        update_folders = []
        for folder in folders.iterator():
            if Path(folder.path).exists():
                folder.updated_at = Now()
                folder.presave()
                update_folders.append(folder)
        Folder.objects.bulk_update(
            update_folders, fields=BULK_UPDATE_FOLDER_MODIFIED_FIELDS
        )
        count = len(update_folders)
        if count:
            self.log.success(f"Modified {count} folders")
        self.changed += count
        self.status_controller.finish(status)

    def move_and_modify_dirs(self):
        """Move files and dirs and modify dirs."""
        # It would be nice to move folders instead of recreating them but it would require
        # an inode map from the snapshots to do correctly.
        self.bulk_folders_moved()
        self.bulk_comics_moved()
        self.bulk_covers_moved()
        self._bulk_folders_modified()
