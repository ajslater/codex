"""Search Index Status Types."""
from codex.librarian.status import StatusTypes


class SearchIndexStatusTypes(StatusTypes):
    """Search Index Status Types."""

    SEARCH_INDEX_CLEAR = "Search index clear"
    SEARCH_INDEX_UPDATE = "Search index update"
    SEARCH_INDEX_FIND_REMOVE = "Search index find ghosts"
    SEARCH_INDEX_REMOVE = "Search index remove ghosts"
    SEARCH_INDEX_OPTIMIZE = "Search index optimize"
