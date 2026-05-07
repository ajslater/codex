"""
Compute the diff between two snapshots.

Supports inode-based move detection and optional device-ignoring for
Docker/complex filesystems.
"""

import os
from dataclasses import dataclass

from django.db.models import Model

from codex.librarian.fs.events import (
    FSChange,
    FSEvent,
)
from codex.librarian.fs.poller.snapshot import Snapshot


@dataclass(frozen=True, slots=True)
class StaleStatRefresh:
    """A path whose stored stat needs refreshing without re-import."""

    path: str
    model: type[Model]
    disk_stat: os.stat_result


_DIFF_FIELD_EVENT_MAP: tuple[tuple[str, FSChange, bool, bool], ...] = (
    # diff_attr, change_type, is_directory, is_cover
    ("files_deleted", FSChange.deleted, False, False),
    ("files_modified", FSChange.modified, False, False),
    ("files_added", FSChange.added, False, False),
    ("covers_deleted", FSChange.deleted, False, True),
    ("covers_modified", FSChange.modified, False, True),
    ("covers_added", FSChange.added, False, True),
    ("dirs_deleted", FSChange.deleted, True, False),
    ("dirs_modified", FSChange.modified, True, False),
)

_DIFF_MOVED_FIELD_EVENT_MAP: tuple[tuple[str, bool, bool], ...] = (
    # diff_attr, is_directory, is_cover
    ("files_moved", False, False),
    ("covers_moved", False, True),
    ("dirs_moved", True, False),
)


@dataclass
class _DiffData:
    """Mutable working state for diff computation."""

    ref: Snapshot
    snapshot: Snapshot
    added: set[str]
    deleted: set[str]
    modified: set[str]
    moved: set[tuple[str, str]]
    unchanged: frozenset[str]


class SnapshotDiff:
    """Diff between a reference snapshot and a new snapshot."""

    def _init_added(self, data: _DiffData, snapshot: Snapshot):
        for p in data.added:
            if snapshot.is_dir(p):
                self.dirs_added.append(p)
            elif snapshot.is_cover(p):
                self.covers_added.append(p)
            else:
                self.files_added.append(p)

    def _init_deleted(self, data: _DiffData, ref: Snapshot):
        for p in data.deleted:
            if ref.is_dir(p):
                self.dirs_deleted.append(p)
            elif ref.is_cover(p):
                self.covers_deleted.append(p)
            else:
                self.files_deleted.append(p)

    def _init_modified(self, data: _DiffData, snapshot: Snapshot):
        for p in data.modified:
            if snapshot.is_dir(p):
                self.dirs_modified.append(p)
            elif snapshot.is_cover(p):
                self.covers_modified.append(p)
            else:
                self.files_modified.append(p)

    def _init_moved(self, data: _DiffData, ref: Snapshot):
        for f, t in data.moved:
            if ref.is_dir(f):
                self.dirs_moved.append((f, t))
            elif ref.is_cover(t):
                self.covers_moved.append((f, t))
            else:
                self.files_moved.append((f, t))

    def __init__(
        self,
        ref: Snapshot,
        snapshot: Snapshot,
    ) -> None:
        """Compute the diff between ref (old/database) and snapshot (new/disk)."""
        data = _DiffData(
            ref=ref,
            snapshot=snapshot,
            added=set(snapshot.paths - ref.paths),
            deleted=set(ref.paths - snapshot.paths),
            modified=set(),
            moved=set(),
            unchanged=frozenset(ref.paths & snapshot.paths),
        )

        self._find_moved_paths(data)
        self._find_modified_paths(data)

        self.dirs_added = []
        self.covers_added = []
        self.files_added = []
        self._init_added(data, snapshot)

        self.dirs_deleted = []
        self.covers_deleted = []
        self.files_deleted = []
        self._init_deleted(data, ref)

        self.dirs_modified = []
        self.covers_modified = []
        self.files_modified = []
        self._init_modified(data, snapshot)

        self.dirs_moved = []
        self.covers_moved = []
        self.files_moved = []
        self._init_moved(data, ref)

        self.stale_stat_refreshes: tuple[StaleStatRefresh, ...] = (
            self._find_stale_stat_refreshes(data)
        )

    @staticmethod
    def _find_stale_stat_refreshes(data: _DiffData) -> tuple[StaleStatRefresh, ...]:
        """
        Identify unchanged-content paths whose stored inode no longer matches disk.

        Filter ``data.unchanged`` down to entries that ``_find_modified_paths``
        did not promote into ``data.modified`` (mtime+size still match).
        When the inode for one of those still differs, the file's
        content is the same but its filesystem identity rotated under
        us — the Docker bind-mount remount case. Without refreshing
        those stats, the DB's inode keyspace stays permanently stale,
        so the next ``_find_moved_paths`` call with a real delete or
        add can match an arbitrary disk path on a numerical
        coincidence (the corruption ``_is_move_compatible`` was added
        to suppress).

        Caller refreshes the DB stat for these paths without bumping
        ``updated_at`` — content hasn't changed. ``model_for_path``
        returns ``None`` for entries with no DB row (e.g. the library
        root itself, which the snapshot adds outside of the per-model
        walk); skip those.
        """
        refreshes: list[StaleStatRefresh] = []
        for path in sorted(data.unchanged - data.modified):
            if data.ref.inode(path) == data.snapshot.inode(path):
                continue
            model = data.ref.model_for_path(path)
            if model is None:
                continue
            refreshes.append(
                StaleStatRefresh(
                    path=path,
                    model=model,
                    disk_stat=data.snapshot.stat(path),
                )
            )
        return tuple(refreshes)

    def _is_stats_equal(self, data: _DiffData, old_path: str, new_path: str) -> bool:
        """Return whether mtime and size match."""
        return data.ref.mtime(old_path) == data.snapshot.mtime(
            new_path
        ) and data.ref.size(old_path) == data.snapshot.size(new_path)

    @staticmethod
    def _is_move_compatible(data: _DiffData, src: str, dest: str) -> bool:
        """
        Reject inode-match pairs that can't be a real rename.

        ``Snapshot._inode`` collapses cross-filesystem inodes into a
        single keyspace (``_ignore_device=True``), so a comic file's
        stored inode can collide with an unrelated directory's inode
        from a different mount. Without these guards the importer
        rewrites the comic's ``path`` and ``stat`` to the directory
        target, leaving a phantom Comic-as-folder row behind and
        spawning a fresh Comic for the original file on the next
        cycle (orphaning bookmarks).

        Two cheap sanity checks make the inode match load-bearing only
        when it's plausibly a rename:

        - File type must match. A real rename never crosses ``stat()``
          file-type bits — files become files, directories stay
          directories. Mode mismatches are always inode collisions.
        - For files, size must match too. Renames preserve size, and
          two unrelated archives are vanishingly unlikely to share an
          exact byte count. Directory ``st_size`` varies with entry
          count and is unreliable, so this check applies to files
          only.
        """
        src_is_dir = data.ref.is_dir(src)
        if src_is_dir != data.snapshot.is_dir(dest):
            return False
        return src_is_dir or data.ref.size(src) == data.snapshot.size(dest)

    def _find_moved_paths(self, data: _DiffData) -> None:
        """Detect moves by matching inodes between deleted and added sets."""
        for old_path in tuple(data.deleted):
            inode = data.ref.inode(old_path)
            new_path = data.snapshot.path(inode)
            if new_path and self._is_move_compatible(data, old_path, new_path):
                data.deleted.remove(old_path)
                data.moved.add((old_path, new_path))

        for new_path in tuple(data.added):
            inode = data.snapshot.inode(new_path)
            old_path = data.ref.path(inode)
            if old_path and self._is_move_compatible(data, old_path, new_path):
                data.added.remove(new_path)
                data.moved.add((old_path, new_path))

    def _find_modified_paths(self, data: _DiffData) -> None:
        """Find paths with changed stats (mtime/size)."""
        for path in data.unchanged:
            if not self._is_stats_equal(data, path, path):
                data.modified.add(path)

        for old_path, new_path in data.moved:
            if not self._is_stats_equal(data, old_path, new_path):
                data.modified.add(new_path)

    def is_empty(self) -> bool:
        """Return True if no changes were detected."""
        return not any(
            (
                self.files_added,
                self.files_deleted,
                self.files_modified,
                self.files_moved,
                self.dirs_added,
                self.dirs_deleted,
                self.dirs_modified,
                self.dirs_moved,
                self.covers_added,
                self.covers_deleted,
                self.covers_modified,
                self.covers_moved,
            )
        )

    def to_events(self) -> tuple[FSEvent, ...]:
        """Convert a SnapshotDiff into a sequence of FSEvents."""
        events: list[FSEvent] = []
        events.extend(
            [
                FSEvent(
                    src_path=src_path,
                    change=change,
                    is_directory=is_dir,
                    is_cover=is_cover,
                )
                for attr, change, is_dir, is_cover in _DIFF_FIELD_EVENT_MAP
                for src_path in getattr(self, attr)
            ]
        )
        events.extend(
            [
                FSEvent(
                    src_path=src_path,
                    change=FSChange.moved,
                    is_directory=is_dir,
                    is_cover=is_cover,
                    dest_path=dest_path,
                )
                for attr, is_dir, is_cover in _DIFF_MOVED_FIELD_EVENT_MAP
                for src_path, dest_path in getattr(self, attr)
            ]
        )
        return tuple(events)
