"""Janitor Status Types."""
from codex.librarian.status import StatusTypes


class JanitorStatusTypes(StatusTypes):
    """Janitor Status Types."""

    CLEAN_SEARCH = "Cleanup Old Search Queries"
    CLEANUP_FK = "Cleanup Foreign Keys"
    CODEX_UPDATE = "Update Codex"
    CODEX_RESTART = "Restart Codex"
    DB_VACUUM = "Vacuum Database"
    DB_BACKUP = "Backup Database"
