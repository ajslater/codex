"""Bulk import and move comics and folders."""

from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.scribe.importer.const import BULK_UPDATE_FOLDER_MODIFIED_FIELDS
from codex.librarian.scribe.importer.moved.folders import MovedFoldersImporter
from codex.librarian.scribe.importer.statii.moved import ImporterUpdateFoldersStatus
from codex.models import Folder


class MovedImporter(MovedFoldersImporter):
    """Methods for moving comics and folders."""

    def _bulk_folders_modified(self) -> int:
        """Update folders stat and nothing else."""
        num_dirs_modified = len(self.task.dirs_modified)
        if not num_dirs_modified:
            return 0
        # Folder mtime updates run in the ``move_and_modify_dirs`` pre-phase,
        # before the per-comic ``read``. The status was previously hijacking
        # ``ImporterUpdateTagsStatus`` (which is reserved for the FK-update
        # phase) and finishing via ``update()`` instead of ``finish()``,
        # leaving an "Update Tags / Folders" row stuck active for the rest
        # of the run. Use a dedicated status and ``finish()`` it cleanly.
        status = ImporterUpdateFoldersStatus(None, num_dirs_modified)
        try:
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
            level = "INFO" if count else "DEBUG"
            self.log.log(level, f"Modified {count} folders")
        finally:
            self.status_controller.finish(status)
        return count

    def move_and_modify_dirs(self) -> None:
        """Move files and dirs and modify dirs."""
        # It would be nice to move folders instead of recreating them but it would require
        # an inode map from the snapshots to do correctly.
        self.counts.folders_moved += self.bulk_folders_moved()
        self.counts.comics_moved += self.bulk_comics_moved()
        self.counts.covers_moved += self.bulk_covers_moved()
        self.counts.folders += self._bulk_folders_modified()
