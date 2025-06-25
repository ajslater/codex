"""Janitor Tasks."""

from dataclasses import dataclass

from codex.librarian.scribe.tasks import ScribeTask


class JanitorTask(ScribeTask):
    """Tasks for the janitor."""


@dataclass
class JanitorCodexUpdateTask(JanitorTask):
    """Task for updater."""

    force: bool = False


class JanitorAdoptOrphanFoldersTask(JanitorTask):
    """Move orphaned folders into a correct tree position."""


class JanitorBackupTask(JanitorTask):
    """Backup the database."""


class JanitorVacuumTask(JanitorTask):
    """Vacuum the database."""


class JanitorCleanFKsTask(JanitorTask):
    """Clean unused foreign keys."""


class JanitorCleanCoversTask(JanitorTask):
    """Clean unused custom covers."""


class JanitorCleanupSessionsTask(JanitorTask):
    """Cleanup Session table."""


class JanitorCleanupBookmarksTask(JanitorTask):
    """Clean unused bookmarks."""


class JanitorForeignKeyCheckTask(JanitorTask):
    """Check and repair foreign keys integrity."""


class JanitorImportForceAllFailedTask(JanitorTask):
    """Force update for failed imports in every library."""


@dataclass
class JanitorIntegrityCheckTask(JanitorTask):
    """Check integrity and warn."""

    long: bool = True


class JanitorFTSIntegrityCheckTask(JanitorTask):
    """Check fts integrity."""


class JanitorFTSRebuildTask(JanitorTask):
    """Rebuild fts table in place."""


class JanitorNightlyTask(JanitorTask):
    """Submit all janitor nightly tasks to the queue."""
