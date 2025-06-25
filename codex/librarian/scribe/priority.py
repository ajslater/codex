"""Priority for Scribe tasks in the PriorityQueue."""

from enum import IntEnum, auto


class ScribeTaskPriority(IntEnum):
    """Priority for Scribe tasks in the PriorityQueue."""

    JanitorClearStatusTask = auto()
    ImportAbortTask = auto()
    SearchIndexAbortTask = auto()
    JanitorNightlyTask = auto()
    JanitorLatestVersionTask = auto()
    JanitorCodexUpdateTask = auto()
    JanitorAdoptOrphanFoldersTask = auto()
    JanitorForeignKeyCheckTask = auto()
    JanitorIntegrityCheckTask = auto()
    JanitorFTSIntegrityCheckTask = auto()
    ForceUpdateAllFailedImportsTask = auto()
    ImportTask = auto()
    LazyImportComicsTask = auto()
    UpdateGroupsTask = auto()
    JanitorCleanFKsTask = auto()
    JanitorCleanCoversTask = auto()
    JanitorCleanupSessionsTask = auto()
    JanitorCleanupBookmarksTask = auto()
    SearchIndexClearTask = auto()
    JanitorFTSRebuildTask = auto()
    SearchIndexRemoveStaleTask = auto()
    SearchIndexUpdateTask = auto()
    SearchIndexOptimizeTask = auto()
    JanitorVacuumTask = auto()
    JanitorBackupTask = auto()
