"""Jantior Statii."""

from abc import ABC

from codex.librarian.scribe.status import ScribeStatus


class JanitorStatus(ScribeStatus, ABC):
    """Jantior Statii."""


class JanitorAdoptOrphanFoldersStatus(JanitorStatus):
    """Janitor Adopt Orphan Folders Status."""

    CODE = "JAF"
    VERB = "Adopt"
    _verbed = "Adopted"
    ITEM_NAME = "orphan folders"


class JanitorCleanupTagsStatus(JanitorStatus):
    """Janitor Cleanup Tags Status."""

    CODE = "JCT"
    VERB = "Cleanup"
    _verbed = "Cleaned up"
    ITEM_NAME = "orphan tags"


class JanitorCodexLatestVersionStatus(JanitorStatus):
    """Janitor Codex Latest Version Status."""

    CODE = "JLV"
    VERB = "Check"
    _verbed = "Checked"
    ITEM_NAME = "Codex latest version"
    SINGLE = True


class JanitorCodexUpdateStatus(JanitorStatus):
    """Janitor Update Codex Software."""

    CODE = "JCU"
    VERB = "Update"
    ITEM_NAME = "Codex server software"
    SINGLE = True
    log_success = True


class JanitorDBOptimizeStatus(JanitorStatus):
    """Janitor DB Optimize."""

    CODE = "JDO"
    VERB = "Optimize"
    ITEM_NAME = "database"
    SINGLE = True
    log_success = True


class JanitorDBBackupStatus(JanitorStatus):
    """Janitor DB Backup."""

    CODE = "JDB"
    VERB = "Backup"
    _verbed = "Backed up"
    ITEM_NAME = "database"
    SINGLE = True


class JanitorCleanupSessionsStatus(JanitorStatus):
    """Janitor Cleanup Sessions Status."""

    CODE = "JRS"
    VERB = "Cleanup"
    _verbed = "Cleaned up"
    ITEM_NAME = "old sessions"


class JanitorCleanupCoversStatus(JanitorStatus):
    """Janitor Cleanup Covers Status."""

    CODE = "JRV"
    VERB = "Cleanup"
    _verbed = "Cleaned up"
    ITEM_NAME = "orphan covers"


class JanitorCleanupBookmarksStatus(JanitorStatus):
    """Janitor Cleanup Bookmarks Status."""

    CODE = "JRB"
    VERB = "Cleanup"
    _verbed = "Cleaned up"
    ITEM_NAME = "orphan bookmarks"


class JanitorDBFKIntegrityStatus(JanitorStatus):
    """Janitor Check DB FK Integrity Status."""

    CODE = "JIF"
    VERB = "Check"
    _verbed = "Checked"
    ITEM_NAME = "integrtity of database foreign keys"
    SINGLE = True


class JanitorDBIntegrityStatus(JanitorStatus):
    """Janitor Check DB Integrity Status."""

    CODE = "JID"
    VERB = "Check"
    _verbed = "Checked"
    ITEM_NAME = "integrity of entire database"
    SINGLE = True


class JanitorDBFTSIntegrityStatus(JanitorStatus):
    """Janitor Check DB FTS Integrity Status."""

    CODE = "JIS"
    VERB = "Check"
    _verbed = "Checked"
    ITEM_NAME = "integrity of full text virtual table"
    SINGLE = True


class JanitorDBFTSRebuildStatus(JanitorStatus):
    """Janitor Rebuild DB FTS Status."""

    CODE = "JSR"
    VERB = "Rebuild"
    _verbed = "Rebuilt"
    ITEM_NAME = "full text search virtual table"
    SINGLE = True
    log_success = True


JANITOR_STATII = (
    JanitorAdoptOrphanFoldersStatus,
    JanitorCleanupTagsStatus,
    JanitorCodexUpdateStatus,
    JanitorCodexLatestVersionStatus,
    JanitorDBOptimizeStatus,
    JanitorDBBackupStatus,
    JanitorCleanupSessionsStatus,
    JanitorCleanupCoversStatus,
    JanitorCleanupBookmarksStatus,
    JanitorDBFKIntegrityStatus,
    JanitorDBIntegrityStatus,
    JanitorDBFTSIntegrityStatus,
    JanitorDBFTSRebuildStatus,
)
