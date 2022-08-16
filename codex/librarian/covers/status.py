"""Cover status types."""
from codex.librarian.status import StatusTypes


class CoverStatusTypes(StatusTypes):
    """Cover Types."""

    CREATE = "Create Covers"
    PURGE = "Remove Covers"
    FIND_ORPHAN = "Find Orphan Covers"
