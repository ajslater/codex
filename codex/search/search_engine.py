"""Locking, Aliasing Xapian Backend."""
from haystack.backends import UnifiedIndex
from haystack.backends.whoosh_backend import WhooshEngine, WhooshSearchBackend

from codex.search.search_indexes import ComicIndex


class CodexWhooshSearchBackend(WhooshSearchBackend):
    """Override methods to use locks and add synonyms to writable database."""

    _SEARCH_FIELD_ALIASES = {
        "ltr": "read_ltr",
        "title": "name",
        "scan": "scan_info",
        "character": "characters",
        "creator": "creators",
        "created": "created_at",
        "finished": "read",
        "genre": "genres",
        "location": "locations",
        "reading": "in_progress",
        "series_group": "series_groups",
        "story_arc": "story_arcs",
        "tag": "tags",
        "team": "teams",
        "updated": "updated_at",
        # OPDS
        "author": "creators",
        "contributor": "creators",
        "category": "characters",  # the most common category, probably
    }

    def _database(self, writable=False):
        """Add synonyms to writable databases."""
        database = super()._database(writable=writable)
        if writable:
            # Ideally this wouldn't be called on remove() or clear()
            for synonym, term in self._SEARCH_FIELD_ALIASES.items():
                database.add_synonym(term, synonym)  # type: ignore
        return database


class CodexUnifiedIndex(UnifiedIndex):
    """Custom Codex Unified Index."""

    def collect_indexes(self):
        """Replace auto app.search_index finding with one exact instance."""
        # Because i moved search_indexes into codex.search
        return [ComicIndex()]


class CodexSearchEngine(WhooshEngine):
    """A search engine with a locking backend."""

    unified_index = CodexUnifiedIndex
