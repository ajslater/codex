"""Locking Xapian Backend."""
# Without this locking xapian throws xapian.DatabaseLockError when
# multiple workers contend for the database.
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
    """Override methods to use locks."""

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


class CodexUnifiedIndex(UnifiedIndex):
    """Custom Codex Unified Index."""

    def collect_indexes(self):
        """Replace auto search_index finding with one exact instance."""
        return [ComicIndex()]


class CodexXapianSearchEngine(BaseEngine):
    """A search engine with a locking backend."""

    backend = CodexXapianSearchBackend
    query = XapianSearchQuery
    unified_index = CodexUnifiedIndex
