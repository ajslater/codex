"""Janitor Status Types."""
from django.db.models import Choices


class JanitorStatusTypes(Choices):
    """Janitor Status Types."""

    CLEANUP_FK = "JTD"
    CODEX_UPDATE = "JCU"
    CODEX_RESTART = "JCR"
    CODEX_STOP = "JCS"
    DB_OPTIMIZE = "JDO"
    DB_BACKUP = "JDB"
    CLEANUP_SESSIONS = "JSD"
