"""Janitor task runner."""

from types import MappingProxyType
from typing import Final

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.librarian.covers.status import FindOrphanCoversStatus, RemoveCoversStatus
from codex.librarian.covers.tasks import CoverRemoveOrphansTask
from codex.librarian.scribe.importer.statii.moved import ImporterMoveFoldersStatus
from codex.librarian.scribe.janitor.status import (
    JanitorAdoptOrphanFoldersStatus,
    JanitorCleanupBookmarksStatus,
    JanitorCleanupCoversStatus,
    JanitorCleanupFavoritesStatus,
    JanitorCleanupSessionsStatus,
    JanitorCleanupSettingsStatus,
    JanitorCleanupTaggingStateStatus,
    JanitorCleanupTagsStatus,
    JanitorCodexLatestVersionStatus,
    JanitorDBBackupStatus,
    JanitorDBFKIntegrityStatus,
    JanitorDBFTSIntegrityStatus,
    JanitorDBIntegrityStatus,
    JanitorDBOptimizeStatus,
    JanitorDumpUserDataStatus,
)
from codex.librarian.scribe.janitor.tasks import (
    JanitorAdoptOrphanFoldersTask,
    JanitorBackupTask,
    JanitorCleanCoversTask,
    JanitorCleanFKsTask,
    JanitorCleanupBookmarksTask,
    JanitorCleanupFavoritesTask,
    JanitorCleanupSessionsTask,
    JanitorCleanupSettingsTask,
    JanitorCleanupTaggingStateTask,
    JanitorCodexUpdateTask,
    JanitorDumpUserDataTask,
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

_JANITOR_STATII: Final = (
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
    JanitorCleanupFavoritesStatus,
    JanitorCleanupTaggingStateStatus,
    SearchIndexCleanStatus,
    SearchIndexSyncUpdateStatus,
    SearchIndexSyncCreateStatus,
    SearchIndexOptimizeStatus,
    JanitorDBOptimizeStatus,
    JanitorDBBackupStatus,
    JanitorDumpUserDataStatus,
    FindOrphanCoversStatus,
    RemoveCoversStatus,
)

_NIGHTLY_TASK_CLASSES: Final[tuple[type[LibrarianTask], ...]] = (
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
    JanitorCleanupFavoritesTask,
    JanitorCleanupTaggingStateTask,
    SearchIndexSyncTask,
    SearchIndexOptimizeTask,
    JanitorVacuumTask,
    JanitorBackupTask,
    JanitorDumpUserDataTask,
    CoverRemoveOrphansTask,
)
_JANITOR_METHOD_MAP: Final[MappingProxyType[type, str]] = MappingProxyType(
    {
        JanitorVacuumTask: "vacuum_db",
        JanitorCleanFKsTask: "cleanup_fks",
        JanitorCleanCoversTask: "cleanup_custom_covers",
        JanitorCleanupSessionsTask: "cleanup_sessions",
        JanitorCleanupBookmarksTask: "cleanup_orphan_bookmarks",
        JanitorCleanupFavoritesTask: "cleanup_orphan_favorites",
        JanitorCleanupSettingsTask: "cleanup_orphan_settings",
        JanitorCleanupTaggingStateTask: "cleanup_tagging_state",
        JanitorImportForceAllFailedTask: "force_update_all_failed_imports",
        JanitorForeignKeyCheckTask: "foreign_key_check",
        JanitorFTSIntegrityCheckTask: "fts_integrity_check",
        JanitorFTSRebuildTask: "fts_rebuild",
        JanitorNightlyTask: "queue_nightly_tasks",
        JanitorDumpUserDataTask: "dump_user_data_sidecar",
    }
)


class Janitor(JanitorCodexUpdate):
    """Janitor inline task runner."""

    def __init__(
        self,
        logger_,
        librarian_queue,
        db_write_lock,
        event,
        online_tag_thread=None,
    ) -> None:
        """Accept the OnlineTagThread back-reference for liveness checks."""
        super().__init__(logger_, librarian_queue, db_write_lock, event)
        self.online_tag_thread = online_tag_thread

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
