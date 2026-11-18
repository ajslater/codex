"""Janitor task runner."""

from types import MappingProxyType
from typing import Final

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.librarian.covers.status import FindOrphanCoversStatus, RemoveCoversStatus
from codex.librarian.covers.tasks import CoverRemoveOrphansTask
from codex.librarian.scribe.importer.statii.moved import ImporterMoveFoldersStatus
from codex.librarian.scribe.janitor.koreader import JanitorKoreaderHash
from codex.librarian.scribe.janitor.status import (
    JanitorAdoptOrphanFoldersStatus,
    JanitorCleanupBookmarksStatus,
    JanitorCleanupCoversStatus,
    JanitorCleanupSessionsStatus,
    JanitorCleanupSettingsStatus,
    JanitorCleanupShelfItemsStatus,
    JanitorCleanupTaggingStateStatus,
    JanitorCleanupTagsStatus,
    JanitorCodexLatestVersionStatus,
    JanitorDBBackupStatus,
    JanitorDBFKIntegrityStatus,
    JanitorDBFTSIntegrityStatus,
    JanitorDBIntegrityStatus,
    JanitorDBOptimizeStatus,
    JanitorDumpUserDataStatus,
    JanitorFolderRelationsStatus,
    JanitorKoreaderHashStatus,
    JanitorReapPendingDeletesStatus,
)
from codex.librarian.scribe.janitor.tasks import (
    JanitorAdoptOrphanFoldersTask,
    JanitorBackupTask,
    JanitorCleanCoversTask,
    JanitorCleanFKsTask,
    JanitorCleanupBookmarksTask,
    JanitorCleanupSessionsTask,
    JanitorCleanupSettingsTask,
    JanitorCleanupShelfItemsTask,
    JanitorCleanupTaggingStateTask,
    JanitorCodexUpdateTask,
    JanitorDumpUserDataTask,
    JanitorFolderRelationsCheckTask,
    JanitorForeignKeyCheckTask,
    JanitorFTSIntegrityCheckTask,
    JanitorFTSRebuildTask,
    JanitorImportForceAllFailedTask,
    JanitorIntegrityCheckTask,
    JanitorKoreaderHashTask,
    JanitorNightlyTask,
    JanitorReapPendingDeletesTask,
    JanitorVacuumTask,
)
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
    JanitorFolderRelationsStatus,
    JanitorDBIntegrityStatus,
    JanitorDBFTSIntegrityStatus,
    JanitorReapPendingDeletesStatus,
    JanitorCleanupTagsStatus,
    JanitorCleanupCoversStatus,
    JanitorCleanupSessionsStatus,
    JanitorCleanupBookmarksStatus,
    JanitorCleanupSettingsStatus,
    JanitorCleanupShelfItemsStatus,
    JanitorCleanupTaggingStateStatus,
    JanitorKoreaderHashStatus,
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

_NIGHTLY_TASKS: Final[tuple[LibrarianTask, ...]] = (
    # Instances, not classes: the version check carries arguments. It
    # forces a fetch (the nightly run is the daily refresh) and asks the
    # fetcher to chain into an update task, which it does only if the
    # Auto Update admin flag is on.
    CodexLatestVersionTask(force=True, update=True),
    JanitorAdoptOrphanFoldersTask(),
    JanitorForeignKeyCheckTask(),
    JanitorFolderRelationsCheckTask(),
    JanitorIntegrityCheckTask(),
    JanitorFTSIntegrityCheckTask(),
    # Before the FK cleanup and the search sync, both of which depend on
    # the rows really being gone: while a stamped comic still exists its
    # Publisher/Imprint/Series/Volume are not orphaned, and the index
    # sync drops FTS rows whose comic no longer exists.
    JanitorReapPendingDeletesTask(),
    JanitorCleanFKsTask(),
    JanitorCleanCoversTask(),
    JanitorCleanupSessionsTask(),
    JanitorCleanupBookmarksTask(),
    JanitorCleanupSettingsTask(),
    JanitorCleanupShelfItemsTask(),
    JanitorCleanupTaggingStateTask(),
    # Does nothing while the KOReader Sync flag is off.
    JanitorKoreaderHashTask(),
    SearchIndexSyncTask(),
    SearchIndexOptimizeTask(),
    JanitorVacuumTask(),
    JanitorBackupTask(),
    JanitorDumpUserDataTask(),
    CoverRemoveOrphansTask(),
)
_JANITOR_METHOD_MAP: Final[MappingProxyType[type, str]] = MappingProxyType(
    {
        JanitorVacuumTask: "vacuum_db",
        JanitorReapPendingDeletesTask: "reap_pending_deletes",
        JanitorCleanFKsTask: "cleanup_fks",
        JanitorCleanCoversTask: "cleanup_custom_covers",
        JanitorCleanupSessionsTask: "cleanup_sessions",
        JanitorCleanupBookmarksTask: "cleanup_orphan_bookmarks",
        JanitorCleanupShelfItemsTask: "cleanup_orphan_shelf_items",
        JanitorCleanupSettingsTask: "cleanup_orphan_settings",
        JanitorCleanupTaggingStateTask: "cleanup_tagging_state",
        JanitorImportForceAllFailedTask: "force_update_all_failed_imports",
        JanitorForeignKeyCheckTask: "foreign_key_check",
        JanitorFolderRelationsCheckTask: "folder_relations_check",
        JanitorFTSIntegrityCheckTask: "fts_integrity_check",
        JanitorFTSRebuildTask: "fts_rebuild",
        JanitorNightlyTask: "queue_nightly_tasks",
        JanitorDumpUserDataTask: "dump_user_data_sidecar",
    }
)


class Janitor(JanitorKoreaderHash):
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
            for task in _NIGHTLY_TASKS:
                self.librarian_queue.put(task)
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
                    self.backup_db(show_status=True, prune=True)
                case JanitorIntegrityCheckTask():
                    self.integrity_check(long=task.long)
                case JanitorCodexUpdateTask():
                    self.update_codex(force=task.force)
                case JanitorKoreaderHashTask():
                    self.koreader_hash_backfill(task)
                case _:
                    self.log.warning(f"Janitor received unknown task {task}")
        except Exception:
            self.log.exception("Janitor task crashed.")
