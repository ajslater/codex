"""Janitor task runner."""

from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.covers.tasks import CoverRemoveOrphansTask
from codex.librarian.janitor.cleanup import TOTAL_NUM_FK_CLASSES, CleanupMixin
from codex.librarian.janitor.failed_imports import UpdateFailedImportsMixin
from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.janitor.tasks import (
    ForceUpdateAllFailedImportsTask,
    JanitorBackupTask,
    JanitorCleanFKsTask,
    JanitorCleanupSessionsTask,
    JanitorClearStatusTask,
    JanitorNightlyTask,
    JanitorRestartTask,
    JanitorShutdownTask,
    JanitorUpdateTask,
    JanitorVacuumTask,
)
from codex.librarian.janitor.update import UpdateMixin
from codex.librarian.janitor.vacuum import VacuumMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import (
    SearchIndexAbortTask,
    SearchIndexMergeTask,
    SearchIndexUpdateTask,
)
from codex.models import AdminFlag, Timestamp
from codex.status import Status

_JANITOR_STATII = (
    Status(JanitorStatusTypes.CLEANUP_FK, 0, TOTAL_NUM_FK_CLASSES),
    Status(JanitorStatusTypes.CLEANUP_SESSIONS),
    Status(JanitorStatusTypes.DB_OPTIMIZE),
    Status(JanitorStatusTypes.DB_BACKUP),
    Status(JanitorStatusTypes.CODEX_UPDATE),
    Status(CoverStatusTypes.FIND_ORPHAN),
    Status(CoverStatusTypes.PURGE_COVERS),
    Status(SearchIndexStatusTypes.SEARCH_INDEX_UPDATE),
    Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE),
    Status(SearchIndexStatusTypes.SEARCH_INDEX_MERGE),
)


class Janitor(CleanupMixin, UpdateMixin, VacuumMixin, UpdateFailedImportsMixin):
    """Janitor inline task runner."""

    def __init__(self, log_queue, librarian_queue):
        """Init logger."""
        self.init_worker(log_queue, librarian_queue)

    def queue_tasks(self):
        """Queue all the janitor tasks."""
        try:
            optimize = AdminFlag.objects.get(
                key=AdminFlag.FlagChoices.SEARCH_INDEX_OPTIMIZE.value
            ).on
            self.status_controller.start_many(_JANITOR_STATII)
            tasks = (
                SearchIndexAbortTask(),
                JanitorCleanFKsTask(),
                JanitorCleanupSessionsTask(),
                JanitorVacuumTask(),
                JanitorBackupTask(),
                JanitorUpdateTask(force=False),
                CoverRemoveOrphansTask(),
                SearchIndexUpdateTask(False),
                SearchIndexMergeTask(optimize),
            )
            for task in tasks:
                self.librarian_queue.put(task)
            Timestamp.touch(Timestamp.TimestampChoices.JANITOR)
        except Exception:
            self.log.exception(f"In {self.__class__.__name__}")

    def run(self, task):
        """Run Janitor tasks as the librarian process directly."""
        try:
            match task:
                case JanitorVacuumTask():
                    self.vacuum_db()
                case JanitorBackupTask():
                    self.backup_db()
                case JanitorUpdateTask():
                    self.update_codex()
                case JanitorRestartTask():
                    self.restart_codex()
                case JanitorShutdownTask():
                    self.shutdown_codex()
                case JanitorCleanFKsTask():
                    self.cleanup_fks()
                case JanitorCleanupSessionsTask():
                    self.cleanup_sessions()
                case JanitorClearStatusTask():
                    self.status_controller.finish_many([])
                case ForceUpdateAllFailedImportsTask():
                    self.force_update_all_failed_imports()
                case JanitorNightlyTask():
                    self.queue_tasks()
                case _:
                    self.log.warning(f"Janitor received unknown task {task}")
        except Exception:
            self.log.exception("Janitor task crashed.")
