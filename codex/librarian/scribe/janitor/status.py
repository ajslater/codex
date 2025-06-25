"""Janitor Status Types."""

from django.db.models import TextChoices


class JanitorStatusTypes(TextChoices):
    """Janitor Status Types."""

    ADOPT_ORPHAN_FOLDERS = "JAF"
    CLEANUP_TAGS = "JTR"
    CODEX_LATEST_VERSION = "JLV"
    CODEX_UPDATE = "JCU"
    DB_OPTIMIZE = "JDO"
    DB_BACKUP = "JDB"
    CLEANUP_SESSIONS = "JSD"
    CLEANUP_COVERS = "JCD"
    CLEANUP_BOOKMARKS = "JCB"
    INTEGRITY_FK = "JIF"
    INTEGRITY_CHECK = "JIC"
    FTS_INTEGRITY_CHECK = "JFC"
    FTS_REBUILD = "JFR"
