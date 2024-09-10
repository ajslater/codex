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
class ForceUpdateAllFailedImportsTask(JanitorTask):
    """Force update for failed imports in every library."""


@dataclass
class JanitorNightlyTask(JanitorTask):
    """Submit all janitor nightly tasks to the queue."""
