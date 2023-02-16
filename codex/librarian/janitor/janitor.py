"""Janitor task runner."""
from codex.librarian.janitor.cleanup import CleanupMixin
from codex.librarian.janitor.failed_imports import UpdateFailedImportsMixin
from codex.librarian.janitor.tasks import (
    ForceUpdateAllFailedImportsTask,
    JanitorBackupTask,
    JanitorCleanFKsTask,
    JanitorCleanupSessionsTask,
    JanitorClearStatusTask,
    JanitorRestartTask,
    JanitorShutdownTask,
    JanitorUpdateTask,
    JanitorVacuumTask,
)
from codex.librarian.janitor.update import UpdateMixin
from codex.librarian.janitor.vacuum import VacuumMixin


class Janitor(CleanupMixin, UpdateMixin, VacuumMixin, UpdateFailedImportsMixin):
    """Janitor inline task runner."""

    def __init__(self, log_queue, librarian_queue):
        """Init logger."""
        self.init_worker(log_queue, librarian_queue)

    def run(self, task):
        """Run Janitor tasks as the librarian process directly."""
        try:
            if isinstance(task, JanitorVacuumTask):
                self.vacuum_db()
            elif isinstance(task, JanitorBackupTask):
                self.backup_db()
            elif isinstance(task, JanitorUpdateTask):
                self.update_codex()
            elif isinstance(task, JanitorRestartTask):
                self.restart_codex()
            elif isinstance(task, JanitorShutdownTask):
                self.shutdown_codex()
            elif isinstance(task, JanitorCleanFKsTask):
                self.cleanup_fks()
            elif isinstance(task, JanitorCleanupSessionsTask):
                self.cleanup_sessions()
            elif isinstance(task, JanitorClearStatusTask):
                self.status_controller.finish_many([])
            elif isinstance(task, ForceUpdateAllFailedImportsTask):
                self.force_update_all_failed_imports()
            else:
                self.log.warning(f"Janitor received unknown task {task}")
        except Exception as exc:
            self.log.error("Janitor task crashed.")
            self.log.exception(exc)
