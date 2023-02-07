"""Janitor Tasks."""
from dataclasses import dataclass


@dataclass
class JanitorTask:
    """Tasks for the janitor."""

    pass


@dataclass
class JanitorBackupTask(JanitorTask):
    """Backup the database."""

    pass


@dataclass
class JanitorRestartTask(JanitorTask):
    """for restart."""

    pass


@dataclass
class JanitorShutdownTask(JanitorTask):
    """for shutdown."""

    pass


@dataclass
class JanitorUpdateTask(JanitorTask):
    """Task for updater."""

    force: bool


@dataclass
class JanitorVacuumTask(JanitorTask):
    """Vacuum the database."""

    pass


@dataclass
class JanitorCleanFKsTask(JanitorTask):
    """Clean unused foreign keys."""

    pass


@dataclass
class JanitorClearStatusTask(JanitorTask):
    """Clear all librarian statuses."""

    pass


@dataclass
class ForceUpdateAllFailedImportsTask(JanitorTask):
    """Force update for failed imports in every library."""

    pass
