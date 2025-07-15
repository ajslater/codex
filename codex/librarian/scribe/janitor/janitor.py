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
    SearchIndexCleanStatus,
    SearchIndexSyncUpdateStatus,
    SearchIndexSyncCreateStatus,
    SearchIndexOptimizeStatus,
    JanitorDBOptimizeStatus,
    JanitorDBBackupStatus,
    FindOrphanCoversStatus,
    RemoveCoversStatus,
)


class Janitor(JanitorCodexUpdate):
    """Janitor inline task runner."""

    def queue_nightly_tasks(self):
        """Queue all the janitor tasks."""
        try:
            self.status_controller.start_many(_JANITOR_STATII)
            tasks = (
                CodexLatestVersionTask(),
                JanitorAdoptOrphanFoldersTask(),
                JanitorForeignKeyCheckTask(),
                JanitorIntegrityCheckTask(),
                JanitorFTSIntegrityCheckTask(),
                JanitorCleanFKsTask(),
                JanitorCleanCoversTask(),
                JanitorCleanupSessionsTask(),
                JanitorCleanupBookmarksTask(),
                SearchIndexSyncTask(),
                SearchIndexOptimizeTask(),
                JanitorVacuumTask(),
                JanitorBackupTask(),
                CoverRemoveOrphansTask(),
            )
            for task in tasks:
                self.librarian_queue.put(task)
            Timestamp.touch(Timestamp.Choices.JANITOR)
        except Exception:
            self.log.exception(f"In {self.__class__.__name__}")

    def handle_task(self, task):  # noqa: PLR0912,C901
        """Run Janitor tasks as the librarian process directly."""
        try:
            match task:
                case JanitorVacuumTask():
                    self.vacuum_db()
                case JanitorBackupTask():
                    self.backup_db(show_status=True)
                case JanitorCleanFKsTask():
                    self.cleanup_fks()
                case JanitorCleanCoversTask():
                    self.cleanup_custom_covers()
                case JanitorCleanupSessionsTask():
                    self.cleanup_sessions()
                case JanitorCleanupBookmarksTask():
                    self.cleanup_orphan_bookmarks()
                case JanitorImportForceAllFailedTask():
                    self.force_update_all_failed_imports()
                case JanitorForeignKeyCheckTask():
                    self.foreign_key_check()
                case JanitorIntegrityCheckTask():
                    self.integrity_check(long=task.long)
                case JanitorFTSIntegrityCheckTask():
                    self.fts_integrity_check()
                case JanitorFTSRebuildTask():
                    self.fts_rebuild()
                case JanitorNightlyTask():
                    self.queue_nightly_tasks()
                case JanitorCodexUpdateTask():
                    self.update_codex(force=task.force)
                case _:
                    self.log.warning(f"Janitor received unknown task {task}")
        except Exception:
            self.log.exception("Janitor task crashed.")
