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


class JanitorDumpUserDataTask(JanitorTask):
    """Snapshot the user-data sidecar from the main DB."""


class JanitorVacuumTask(JanitorTask):
    """Vacuum the database."""


class JanitorCleanFKsTask(JanitorTask):
    """Clean unused foreign keys."""


class JanitorSyncReadingListsTask(JanitorTask):
    """Sync the reading lists from story-arc tags."""


class JanitorRematchReadingListsTask(JanitorTask):
    """Match every reading list's missing entries again."""


class JanitorRefreshReadingListsTask(JanitorTask):
    """Fetch again the remote reading list sources due a refresh."""


class JanitorCleanCoversTask(JanitorTask):
    """Clean unused custom covers."""


class JanitorCleanupSessionsTask(JanitorTask):
    """Cleanup Session table."""


class JanitorCleanupBookmarksTask(JanitorTask):
    """Clean unused bookmarks."""


class JanitorCleanupSettingsTask(JanitorTask):
    """Clean orphan settings rows."""


class JanitorCleanupShelfItemsTask(JanitorTask):
    """Clean shelf items whose target row no longer exists."""


class JanitorKoreaderHashTask(JanitorTask):
    """Backfill KOReader sync hashes for comics that lack them."""


class JanitorCleanupTaggingStateTask(JanitorTask):
    """Clear orphan online tagging session and prompt state."""


class JanitorForeignKeyCheckTask(JanitorTask):
    """Check and repair foreign keys integrity."""


class JanitorFolderRelationsCheckTask(JanitorTask):
    """Check and repair drifted comic↔folder relations."""


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


class JanitorReapPendingDeletesTask(JanitorTask):
    """Really delete rows whose retention window has expired."""


class JanitorNightlyTask(JanitorTask):
    """Submit all janitor nightly tasks to the queue."""
