"""Priority for Scribe tasks in the PriorityQueue."""

from datetime import UTC, datetime

from codex.librarian.scribe.importer.tasks import (
    ImportTask,
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
    JanitorCodexUpdateTask,
    JanitorForeignKeyCheckTask,
    JanitorFTSIntegrityCheckTask,
    JanitorFTSRebuildTask,
    JanitorImportForceAllFailedTask,
    JanitorIntegrityCheckTask,
    JanitorNightlyTask,
    JanitorVacuumTask,
)
from codex.librarian.scribe.search.tasks import (
    SearchIndexCleanStaleTask,
    SearchIndexClearTask,
    SearchIndexOptimizeTask,
    SearchIndexSyncTask,
)
from codex.librarian.scribe.tasks import (
    ForceUpdateComicsTask,
    ImportAbortTask,
    LazyImportComicsTask,
    ScribeTask,
    SearchIndexSyncAbortTask,
    UpdateGroupsTask,
)

_SCRIBE_TASK_PRIORITY = (
    ImportAbortTask,
    SearchIndexSyncAbortTask,
    JanitorNightlyTask,
    JanitorCodexUpdateTask,
    JanitorAdoptOrphanFoldersTask,
    JanitorForeignKeyCheckTask,
    JanitorIntegrityCheckTask,
    JanitorFTSIntegrityCheckTask,
    JanitorFTSRebuildTask,
    JanitorImportForceAllFailedTask,
    ForceUpdateComicsTask,
    ImportTask,
    LazyImportComicsTask,
    UpdateGroupsTask,
    JanitorCleanFKsTask,
    JanitorCleanCoversTask,
    JanitorCleanupSessionsTask,
    JanitorCleanupBookmarksTask,
    JanitorCleanupSettingsTask,
    JanitorCleanupFavoritesTask,
    SearchIndexClearTask,
    SearchIndexCleanStaleTask,
    SearchIndexSyncTask,
    SearchIndexOptimizeTask,
    JanitorVacuumTask,
    JanitorBackupTask,
)


def get_task_priority(task: ScribeTask) -> tuple[int, float]:
    """Get task priority by index."""
    now = datetime.now(tz=UTC).timestamp()
    priority = _SCRIBE_TASK_PRIORITY.index(type(task))
    return priority, now
