"""Locking Xapian Backend."""
# Without this locking xapian throws xapian.DatabaseLockError when
# multiple workers contend for the database.
from fcntl import LOCK_EX, LOCK_UN, flock
from pathlib import Path

from xapian_backend import XapianSearchBackend, XapianSearchQuery

from codex._vendor.haystack.backends import BaseEngine


class FileLock(object):
    """A basic flock file lock."""

    def __init__(self, path):
        """Store the path."""
        self.path = path

    def __enter__(self):
        """Enter the lock."""
        self.path.touch()
        self.file = self.path.open("r")
        flock(self.file, LOCK_EX)

    def __exit__(self, _exc_type, _exc_value, _traceback):
        """Exit the lock."""
        flock(self.file, LOCK_UN)
        self.file.close()


class CodexXapianSearchBackend(XapianSearchBackend):
    """Override methods to use locks."""

    def __init__(self, *args, **kwargs):
        """Set the lockfile."""
        super().__init__(*args, **kwargs)
        self.lockfile = Path(self.path) / "lockfile"  # type: ignore

    def update(self, index, iterable, commit=True):
        """Use lock with update."""
        with FileLock(path=self.lockfile):
            super().update(index=index, iterable=iterable, commit=commit)

    def remove(self, obj, commit=True):
        """Use lock with remove."""
        with FileLock(path=self.lockfile):
            return super().remove(obj=obj, commit=commit)


class CodexXapianSearchEngine(BaseEngine):
    """A search engine with a locking backend."""

    backend = CodexXapianSearchBackend
    query = XapianSearchQuery
