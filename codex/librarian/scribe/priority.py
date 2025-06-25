"""Priority for Scribe tasks in the PriorityQueue."""

from codex.librarian.scribe.importer.tasks import (
    ImportTask,
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
from codex.librarian.scribe.search.tasks import (
    SearchIndexClearTask,
    SearchIndexOptimizeTask,
    SearchIndexRemoveStaleTask,
    SearchIndexUpdateTask,
)
from codex.librarian.scribe.tasks import (
    ImportAbortTask,
    LazyImportComicsTask,
    ScribeTask,
    SearchIndexAbortTask,
    UpdateGroupsTask,
)

_SCRIBE_TASK_PRIORITY = (
    ImportAbortTask,
    SearchIndexAbortTask,
    JanitorNightlyTask,
    JanitorCodexUpdateTask,
    JanitorAdoptOrphanFoldersTask,
    JanitorForeignKeyCheckTask,
    JanitorIntegrityCheckTask,
    JanitorFTSIntegrityCheckTask,
    JanitorImportForceAllFailedTask,
    ImportTask,
    LazyImportComicsTask,
    UpdateGroupsTask,
    JanitorCleanFKsTask,
    JanitorCleanCoversTask,
    JanitorCleanupSessionsTask,
    JanitorCleanupBookmarksTask,
    SearchIndexClearTask,
    JanitorFTSRebuildTask,
    SearchIndexRemoveStaleTask,
    SearchIndexUpdateTask,
    SearchIndexOptimizeTask,
    JanitorVacuumTask,
    JanitorBackupTask,
)


def get_task_priority(task: ScribeTask):
    """Get task priority by index."""
    return _SCRIBE_TASK_PRIORITY.index(type(task))
