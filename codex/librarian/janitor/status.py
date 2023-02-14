"""Janitor Status Types."""
from codex.librarian.status import StatusTypes


class JanitorStatusTypes(StatusTypes):
    """Janitor Status Types."""

    CLEANUP_FK = "Cleanup Foreign Keys"
    CODEX_UPDATE = "Update Codex"
    CODEX_RESTART = "Restart Codex"
    CODEX_STOP = "Stop Codex"
    DB_VACUUM = "Vacuum Database"
    DB_BACKUP = "Backup Database"
    CLEANUP_SESSIONS = "Cleanup Sessions"
