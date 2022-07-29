"""Janitor Tasks."""
from abc import ABC
from dataclasses import dataclass


@dataclass
class JanitorTask(ABC):
    """Tasks for the janitor."""

    pass


@dataclass
class JanitorBackupTask(JanitorTask):
    """Backup the database."""

    pass


@dataclass
class JanitorRestartTask:
    """for restart."""

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
class JanitorCleanSearchTask(JanitorTask):
    """Clean the search db."""

    pass


@dataclass
class JanitorCleanFKsTask(JanitorTask):
    """Clean unused foreign keys."""

    pass


@dataclass
class JanitorClearStatusTask(JanitorTask):
    """Clear all librarian statuses."""

    pass
