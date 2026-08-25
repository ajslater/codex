"""Priority for Scribe tasks in the PriorityQueue."""

from datetime import UTC, datetime
from itertools import count

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
    JanitorCleanupTaggingStateTask,
    JanitorCodexUpdateTask,
    JanitorDumpUserDataTask,
    JanitorFolderRelationsCheckTask,
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
    BulkTagWriteTask,
    ForceUpdateComicsTask,
    ImportAbortTask,
    LazyImportComicsTask,
    ScribeTask,
    SearchIndexSyncAbortTask,
    TagWriteAbortTask,
    UpdateCollectionsTask,
)

_SCRIBE_TASK_PRIORITY = (
    ImportAbortTask,
    SearchIndexSyncAbortTask,
    JanitorNightlyTask,
    JanitorCodexUpdateTask,
    JanitorAdoptOrphanFoldersTask,
    JanitorForeignKeyCheckTask,
    JanitorFolderRelationsCheckTask,
    JanitorIntegrityCheckTask,
    JanitorFTSIntegrityCheckTask,
    JanitorFTSRebuildTask,
    JanitorImportForceAllFailedTask,
    TagWriteAbortTask,
    ForceUpdateComicsTask,
    BulkTagWriteTask,
    ImportTask,
    LazyImportComicsTask,
    UpdateCollectionsTask,
    JanitorCleanFKsTask,
    JanitorCleanCoversTask,
    JanitorCleanupSessionsTask,
    JanitorCleanupBookmarksTask,
    JanitorCleanupSettingsTask,
    JanitorCleanupFavoritesTask,
    JanitorCleanupTaggingStateTask,
    SearchIndexClearTask,
    SearchIndexCleanStaleTask,
    SearchIndexSyncTask,
    SearchIndexOptimizeTask,
    JanitorVacuumTask,
    JanitorBackupTask,
    JanitorDumpUserDataTask,
)

# Final element of every priority tuple. Tasks are pushed onto a heap as
# ``(priority, task)``; when two priorities compare equal the heap falls
# through to comparing the tasks themselves, and ScribeTask dataclasses
# define no ordering — a ``TypeError`` in the routing thread that loses the
# task. Timestamps tie more often than they look like they would (they are
# truncated, and a clock can step backwards), so carry a strictly monotonic
# counter that can never tie. ``next`` on an ``itertools.count`` is atomic.
_TIE_BREAKER = count()


def get_task_priority(task: ScribeTask) -> tuple[int, float, int]:
    """Get task priority by index."""
    now = datetime.now(tz=UTC).timestamp()
    priority = _SCRIBE_TASK_PRIORITY.index(type(task))
    return priority, now, next(_TIE_BREAKER)
