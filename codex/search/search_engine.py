"""Locking, Aliasing Xapian Backend."""
# Without this locking xapian throws xapian.DatabaseLockError when
# multiple workers contend for the database.
# File locks have been submitted upstream, awaiting a new release.
from pathlib import Path

from filelock import FileLock
from haystack.backends import BaseEngine, UnifiedIndex
from xapian_backend import XapianSearchBackend, XapianSearchQuery

from codex.search.search_indexes import ComicIndex


def filelocked(func):
    """Decorate filelocked methods."""

    def wrapper(self, *args, **kwargs):
        self.lockfile.parent.mkdir(parents=True, exist_ok=True)
        self.lockfile.touch()
        with self.filelock:
            func(self, *args, **kwargs)

    return wrapper


class CodexXapianSearchBackend(XapianSearchBackend):
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

    def __init__(self, *args, **kwargs):
        """Set the lockfile."""
        super().__init__(*args, **kwargs)
        if not self.path:
            raise ValueError("Haystack PATH not set in settings.")
        self.lockfile = Path(self.path) / "lockfile"
        self.filelock = FileLock(self.lockfile)

    @filelocked
    def update(self, index, iterable, commit=True):
        """Use lock with update."""
        return super().update(index, iterable, commit=commit)

    @filelocked
    def remove(self, obj, commit=True):
        """Use lock with remove."""
        return super().remove(obj, commit=commit)

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


class CodexXapianSearchEngine(BaseEngine):
    """A search engine with a locking backend."""

    backend = CodexXapianSearchBackend
    query = XapianSearchQuery
    unified_index = CodexUnifiedIndex
