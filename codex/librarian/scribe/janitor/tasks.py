"""Janitor Tasks."""

from dataclasses import dataclass

from codex.librarian.scribe.tasks import ScribeTask


@dataclass(order=True)
class JanitorTask(ScribeTask):
    """Tasks for the janitor."""


@dataclass(order=True)
class JanitorCodexUpdateTask(JanitorTask):
    """Task for updater."""

    force: bool = False


@dataclass(order=True)
class JanitorAdoptOrphanFoldersTask(JanitorTask):
    """Move orphaned folders into a correct tree position."""


@dataclass(order=True)
class JanitorBackupTask(JanitorTask):
    """Backup the database."""


@dataclass(order=True)
class JanitorVacuumTask(JanitorTask):
    """Vacuum the database."""


@dataclass(order=True)
class JanitorCleanFKsTask(JanitorTask):
    """Clean unused foreign keys."""


@dataclass(order=True)
class JanitorCleanCoversTask(JanitorTask):
    """Clean unused custom covers."""


@dataclass(order=True)
class JanitorCleanupSessionsTask(JanitorTask):
    """Cleanup Session table."""


@dataclass(order=True)
class JanitorCleanupBookmarksTask(JanitorTask):
    """Clean unused bookmarks."""


@dataclass(order=True)
class ForceUpdateAllFailedImportsTask(JanitorTask):
    """Force update for failed imports in every library."""


@dataclass(order=True)
class JanitorForeignKeyCheckTask(JanitorTask):
    """Check and repair foreign keys integrity."""


@dataclass(order=True)
class JanitorIntegrityCheckTask(JanitorTask):
    """Check integrity and warn."""

    long: bool = True


@dataclass(order=True)
class JanitorFTSIntegrityCheckTask(JanitorTask):
    """Check fts integrity."""


@dataclass(order=True)
class JanitorFTSRebuildTask(JanitorTask):
    """Rebuild fts table in place."""


@dataclass(order=True)
class JanitorNightlyTask(JanitorTask):
    """Submit all janitor nightly tasks to the queue."""
