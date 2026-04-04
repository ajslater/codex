"""Janitor task runner."""

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.librarian.covers.status import FindOrphanCoversStatus, RemoveCoversStatus
from codex.librarian.covers.tasks import CoverRemoveOrphansTask
from codex.librarian.scribe.importer.statii.moved import ImporterMoveFoldersStatus
from codex.librarian.scribe.janitor.status import (
    JanitorAdoptOrphanFoldersStatus,
    JanitorCleanupBookmarksStatus,
    JanitorCleanupCoversStatus,
    JanitorCleanupSessionsStatus,
    JanitorCleanupSettingsStatus,
    JanitorCleanupTagsStatus,
    JanitorCodexLatestVersionStatus,
    JanitorDBBackupStatus,
    JanitorDBFKIntegrityStatus,
    JanitorDBFTSIntegrityStatus,
    JanitorDBIntegrityStatus,
    JanitorDBOptimizeStatus,
)
from codex.librarian.scribe.janitor.tasks import (
    JanitorAdoptOrphanFoldersTask,
    JanitorBackupTask,
    JanitorCleanCoversTask,
    JanitorCleanFKsTask,
    JanitorCleanupBookmarksTask,
    JanitorCleanupSessionsTask,
    JanitorCleanupSettingsTask,
    JanitorCodexUpdateTask,
    JanitorForeignKeyCheckTask,
    JanitorFTSIntegrityCheckTask,
    JanitorFTSRebuildTask,
    JanitorImportForceAllFailedTask,
    JanitorIntegrityCheckTask,
    JanitorNightlyTask,
    JanitorVacuumTask,
)
from codex.librarian.scribe.janitor.update import JanitorCodexUpdate
from codex.librarian.scribe.search.status import (
    SearchIndexCleanStatus,
    SearchIndexOptimizeStatus,
    SearchIndexSyncCreateStatus,
    SearchIndexSyncUpdateStatus,
)
from codex.librarian.scribe.search.tasks import (
    SearchIndexOptimizeTask,
    SearchIndexSyncTask,
)
from codex.librarian.tasks import LibrarianTask
from codex.models import Timestamp

_JANITOR_STATII = (
    JanitorCodexLatestVersionStatus,
    JanitorAdoptOrphanFoldersStatus,
    ImporterMoveFoldersStatus,
    JanitorDBFKIntegrityStatus,
    JanitorDBIntegrityStatus,
    JanitorDBFTSIntegrityStatus,
    JanitorCleanupTagsStatus,
    JanitorCleanupCoversStatus,
    JanitorCleanupSessionsStatus,
    JanitorCleanupBookmarksStatus,
    JanitorCleanupSettingsStatus,
    SearchIndexCleanStatus,
    SearchIndexSyncUpdateStatus,
    SearchIndexSyncCreateStatus,
    SearchIndexOptimizeStatus,
    JanitorDBOptimizeStatus,
    JanitorDBBackupStatus,
    FindOrphanCoversStatus,
    RemoveCoversStatus,
)

_NIGHTLY_TASK_CLASSES: tuple[type[LibrarianTask], ...] = (
    CodexLatestVersionTask,
    JanitorAdoptOrphanFoldersTask,
    JanitorForeignKeyCheckTask,
    JanitorIntegrityCheckTask,
    JanitorFTSIntegrityCheckTask,
    JanitorCleanFKsTask,
    JanitorCleanCoversTask,
    JanitorCleanupSessionsTask,
    JanitorCleanupBookmarksTask,
    JanitorCleanupSettingsTask,
    SearchIndexSyncTask,
    SearchIndexOptimizeTask,
    JanitorVacuumTask,
    JanitorBackupTask,
    CoverRemoveOrphansTask,
)
_JANITOR_METHOD_MAP: dict[type, str] = {
    JanitorVacuumTask: "vacuum_db",
    JanitorCleanFKsTask: "cleanup_fks",
    JanitorCleanCoversTask: "cleanup_custom_covers",
    JanitorCleanupSessionsTask: "cleanup_sessions",
    JanitorCleanupBookmarksTask: "cleanup_orphan_bookmarks",
    JanitorCleanupSettingsTask: "cleanup_orphan_settings",
    JanitorImportForceAllFailedTask: "force_update_all_failed_imports",
    JanitorForeignKeyCheckTask: "foreign_key_check",
    JanitorFTSIntegrityCheckTask: "fts_integrity_check",
    JanitorFTSRebuildTask: "fts_rebuild",
    JanitorNightlyTask: "queue_nightly_tasks",
}


class Janitor(JanitorCodexUpdate):
    """Janitor inline task runner."""

    def queue_nightly_tasks(self) -> None:
        """Queue all the janitor tasks."""
        try:
            self.status_controller.start_many(_JANITOR_STATII)
            for task_class in _NIGHTLY_TASK_CLASSES:
                self.librarian_queue.put(task_class())
            Timestamp.touch(Timestamp.Choices.JANITOR)
        except Exception:
            self.log.exception(f"In {self.__class__.__name__}")

    def handle_task(self, task) -> None:
        """Run Janitor tasks as the librarian process directly."""
        try:
            # Simple task dispatch
            if method_name := _JANITOR_METHOD_MAP.get(type(task)):
                method = getattr(self, method_name)
                method()
                return

            # Tasks with special parameters
            match task:
                case JanitorBackupTask():
                    self.backup_db(show_status=True)
                case JanitorIntegrityCheckTask():
                    self.integrity_check(long=task.long)
                case JanitorCodexUpdateTask():
                    self.update_codex(force=task.force)
                case _:
                    self.log.warning(f"Janitor received unknown task {task}")
        except Exception:
            self.log.exception("Janitor task crashed.")
