"""Janitor Tasks."""

from dataclasses import dataclass


@dataclass
class JanitorTask:
    """Tasks for the janitor."""


@dataclass
class JanitorLatestVersionTask(JanitorTask):
    """Get the latest version."""

    force: bool = False


@dataclass
class JanitorUpdateTask(JanitorTask):
    """Task for updater."""

    force: bool = False


@dataclass
class JanitorBackupTask(JanitorTask):
    """Backup the database."""


@dataclass
class JanitorRestartTask(JanitorTask):
    """for restart."""


@dataclass
class JanitorShutdownTask(JanitorTask):
    """for shutdown."""


@dataclass
class JanitorVacuumTask(JanitorTask):
    """Vacuum the database."""


@dataclass
class JanitorCleanFKsTask(JanitorTask):
    """Clean unused foreign keys."""


@dataclass
class JanitorCleanCoversTask(JanitorTask):
    """Clean unused custom covers."""


@dataclass
class JanitorClearStatusTask(JanitorTask):
    """Clear all librarian statuses."""


@dataclass
class JanitorCleanupSessionsTask(JanitorTask):
    """Cleanup Session table."""


@dataclass
class JanitorCleanupBookmarksTask(JanitorTask):
    """Clean unused bookmarks."""


@dataclass
class ForceUpdateAllFailedImportsTask(JanitorTask):
    """Force update for failed imports in every library."""


@dataclass
class JanitorForeignKeyCheck(JanitorTask):
    """Check and repair foreign keys integrity."""


@dataclass
class JanitorIntegrityCheck(JanitorTask):
    """Check integrity and warn."""

    long: bool = True


@dataclass
class JanitorFTSIntegrityCheck(JanitorTask):
    """Check fts integrity."""


@dataclass
class JanitorFTSRebuildTask(JanitorTask):
    """Rebuild fts table in place."""


@dataclass
class JanitorNightlyTask(JanitorTask):
    """Submit all janitor nightly tasks to the queue."""


@dataclass
class JanitorAdoptOrphanFoldersFinishedTask(JanitorTask):
    """Signals to the Janitor that the Adopt Orphan Folders task is finished."""


@dataclass
class JanitorSearchOptimizeFinishedTask(JanitorTask):
    """Signals to the Janitor that the Search Optimize task is finished."""
