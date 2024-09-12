"""Janitor Status Types."""

from django.db.models import Choices


class JanitorStatusTypes(Choices):
    """Janitor Status Types."""

    CLEANUP_FK = "JTD"
    CODEX_LATEST_VERSION = "JLV"
    CODEX_UPDATE = "JCU"
    CODEX_RESTART = "JCR"
    CODEX_STOP = "JCS"
    DB_OPTIMIZE = "JDO"
    DB_BACKUP = "JDB"
    CLEANUP_SESSIONS = "JSD"
    CLEANUP_COVERS = "JCD"
    CLEANUP_BOOKMARKS = "JCB"
    INTEGRITY_FK = "JIF"
    INTEGRITY_CHECK = "JIC"
    FTS_INTEGRITY_CHECK = "JFC"
    FTS_REBUILD = "JFR"
