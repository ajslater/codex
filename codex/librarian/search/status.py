"""Search Index Status Types."""
from codex.librarian.status import StatusTypes


class SearchIndexStatusTypes(StatusTypes):
    """Search Index Status Types."""

    SEARCH_INDEX_CLEAR = "Search index clear"
    SEARCH_INDEX_PREPARE = "Search index prepare"
    SEARCH_INDEX_COMMIT = "Search index commit"
    SEARCH_INDEX_OPTIMIZE = "Search index optimize"
