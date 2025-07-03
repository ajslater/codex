"""Janitor task runner."""

from codex.librarian.bookmark.tasks import CodexLatestVersionTask
from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.covers.tasks import CoverRemoveOrphansTask
from codex.librarian.scribe.importer.status import ImporterStatusTypes
from codex.librarian.scribe.janitor.status import JanitorStatusTypes
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
from codex.librarian.scribe.search.status import SearchIndexStatusTypes
from codex.librarian.scribe.search.tasks import (
    SearchIndexOptimizeTask,
)
from codex.librarian.status import Status
from codex.models import Timestamp

_JANITOR_STATII = (
    Status(JanitorStatusTypes.CODEX_LATEST_VERSION),
    Status(JanitorStatusTypes.INTEGRITY_FK),
    Status(JanitorStatusTypes.INTEGRITY_CHECK),
    Status(JanitorStatusTypes.CLEANUP_COVERS),
    Status(JanitorStatusTypes.CLEANUP_TAGS),
    Status(JanitorStatusTypes.CLEANUP_SESSIONS),
    Status(JanitorStatusTypes.CLEANUP_BOOKMARKS),
    Status(JanitorStatusTypes.DB_OPTIMIZE),
    Status(JanitorStatusTypes.DB_BACKUP),
    Status(CoverStatusTypes.FIND_ORPHAN_COVERS),
    Status(CoverStatusTypes.PURGE_COVERS),
    Status(JanitorStatusTypes.ADOPT_ORPHAN_FOLDERS),
    Status(ImporterStatusTypes.MOVE_FOLDERS),
    Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAN),
    Status(SearchIndexStatusTypes.SEARCH_INDEX_OPTIMIZE),
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
