"""Janitor task runner."""

from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.covers.tasks import CoverRemoveOrphansTask
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.importer.tasks import (
    AdoptOrphanFoldersTask,
)
from codex.librarian.janitor.cleanup import TOTAL_NUM_FK_CLASSES, CleanupMixin
from codex.librarian.janitor.failed_imports import UpdateFailedImportsMixin
from codex.librarian.janitor.integrity import IntegrityMixin
from codex.librarian.janitor.latest_version import LatestVersionMixin
from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.janitor.tasks import (
    ForceUpdateAllFailedImportsTask,
    JanitorAdoptOrphanFoldersFinishedTask,
    JanitorBackupTask,
    JanitorCleanCoversTask,
    JanitorCleanFKsTask,
    JanitorCleanupBookmarksTask,
    JanitorCleanupSessionsTask,
    JanitorClearStatusTask,
    JanitorForeignKeyCheck,
    JanitorFTSIntegrityCheck,
    JanitorFTSRebuildTask,
    JanitorIntegrityCheck,
    JanitorLatestVersionTask,
    JanitorNightlyTask,
    JanitorRestartTask,
    JanitorSearchOptimizeFinishedTask,
    JanitorShutdownTask,
    JanitorUpdateTask,
    JanitorVacuumTask,
)
from codex.librarian.janitor.update import UpdateMixin
from codex.librarian.janitor.vacuum import VacuumMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import (
    SearchIndexAbortTask,
    SearchIndexOptimizeTask,
    SearchIndexUpdateTask,
)
from codex.models import Timestamp
from codex.status import Status

_JANITOR_STATII = (
    Status(JanitorStatusTypes.CODEX_LATEST_VERSION),
    Status(JanitorStatusTypes.INTEGRITY_FK),
    Status(JanitorStatusTypes.INTEGRITY_CHECK),
    Status(JanitorStatusTypes.CLEANUP_FK, 0, TOTAL_NUM_FK_CLASSES),
    Status(JanitorStatusTypes.CLEANUP_COVERS),
    Status(JanitorStatusTypes.CLEANUP_SESSIONS),
    Status(JanitorStatusTypes.CLEANUP_BOOKMARKS),
    Status(JanitorStatusTypes.DB_OPTIMIZE),
    Status(JanitorStatusTypes.DB_BACKUP),
    Status(JanitorStatusTypes.CODEX_UPDATE),
    Status(CoverStatusTypes.FIND_ORPHAN),
    Status(CoverStatusTypes.PURGE_COVERS),
    Status(ImportStatusTypes.ADOPT_FOLDERS),
    Status(ImportStatusTypes.DIRS_MOVED),
    Status(SearchIndexStatusTypes.SEARCH_INDEX_UPDATE),
    Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE),
    Status(SearchIndexStatusTypes.SEARCH_INDEX_OPTIMIZE),
)


class Janitor(
    CleanupMixin,
    LatestVersionMixin,
    UpdateMixin,
    UpdateFailedImportsMixin,
    VacuumMixin,
    IntegrityMixin,
):
    """Janitor inline task runner."""

    def __init__(self, log_queue, librarian_queue):
        """Init logger."""
        self.init_worker(log_queue, librarian_queue)

    def queue_tasks(self):
        """Queue all the janitor tasks."""
        try:
            self.status_controller.start_many(_JANITOR_STATII)
            tasks = (
                SearchIndexAbortTask(),
                JanitorLatestVersionTask(),
                JanitorUpdateTask(),
                JanitorForeignKeyCheck(),
                JanitorIntegrityCheck(),
                JanitorFTSIntegrityCheck(),
                JanitorCleanFKsTask(),
                JanitorCleanCoversTask(),
                JanitorCleanupSessionsTask(),
                JanitorCleanupBookmarksTask(),
                AdoptOrphanFoldersTask(janitor=True),
                CoverRemoveOrphansTask(),
            )
            for task in tasks:
                self.librarian_queue.put(task)
            Timestamp.touch(Timestamp.TimestampChoices.JANITOR)
        except Exception:
            self.log.exception(f"In {self.__class__.__name__}")

    def run(self, task):  # noqa: PLR0912,C901
        """Run Janitor tasks as the librarian process directly."""
        try:
            match task:
                case JanitorVacuumTask():
                    self.vacuum_db()
                case JanitorBackupTask():
                    self.backup_db()
                case JanitorLatestVersionTask():
                    self.update_latest_version(task.force)
                case JanitorUpdateTask():
                    self.update_codex(task.force)
                case JanitorRestartTask():
                    self.restart_codex()
                case JanitorShutdownTask():
                    self.shutdown_codex()
                case JanitorCleanFKsTask():
                    self.cleanup_fks()
                case JanitorCleanCoversTask():
                    self.cleanup_custom_covers()
                case JanitorCleanupSessionsTask():
                    self.cleanup_sessions()
                case JanitorCleanupBookmarksTask():
                    self.cleanup_orphan_bookmarks()
                case JanitorClearStatusTask():
                    self.status_controller.finish_many([])
                case ForceUpdateAllFailedImportsTask():
                    self.force_update_all_failed_imports()
                case JanitorForeignKeyCheck():
                    self.foreign_key_check()
                case JanitorIntegrityCheck():
                    self.integrity_check(task.long)
                case JanitorFTSIntegrityCheck():
                    self.fts_integrity_check()
                case JanitorFTSRebuildTask():
                    self.fts_rebuild()
                case JanitorNightlyTask():
                    self.queue_tasks()
                case JanitorAdoptOrphanFoldersFinishedTask():
                    next_tasks = (
                        SearchIndexAbortTask(),
                        SearchIndexUpdateTask(),
                        SearchIndexOptimizeTask(janitor=True),
                    )
                    for next_task in next_tasks:
                        self.librarian_queue.put(next_task)
                case JanitorSearchOptimizeFinishedTask():
                    next_tasks = (JanitorVacuumTask(), JanitorBackupTask())
                    for next_task in next_tasks:
                        self.librarian_queue.put(next_task)
                case _:
                    self.log.warning(f"Janitor received unknown task {task}")
        except Exception:
            self.log.exception("Janitor task crashed.")
