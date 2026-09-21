"""
Compute the diff between two snapshots.

Moves are detected in two tiers. An inode is identity, so it pairs a
move outright. A move that lost its inode — a copy-then-delete, a
cross-device ``mv``, a remount that rotated the inode space — falls
through to a signature of name, size and mtime, which only pairs when it
is unique on both sides. Whatever stays unpaired becomes a delete plus an
add, which costs the comic its bookmarks.

Also supports optional device-ignoring for Docker/complex filesystems.
"""

import os
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import PurePath

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


@dataclass(frozen=True, slots=True)
class RevivedPath:
    """A stamped row whose file is back on disk."""

    path: str
    model: type[Model]


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
        *,
        force: bool = False,
    ) -> None:
        """
        Compute the diff between ref (old/database) and snapshot (new/disk).

        ``force`` is the admin's Force Update: report every surviving
        path as modified so the importer re-reads it. Keyword-only
        because the two snapshots are the argument list callers know.
        """
        data = _DiffData(
            ref=ref,
            snapshot=snapshot,
            added=set(snapshot.paths - ref.paths),
            deleted=set(ref.paths - snapshot.paths),
            modified=set(),
            moved=set(),
            unchanged=frozenset(ref.paths & snapshot.paths),
        )

        # A row already stamped as missing has been reported once. It
        # stays in ``ref.paths`` so a returning file keeps its row, but
        # re-reporting it every poll would pay the second look's wait
        # each time, re-fire the mass-delete warning, keep the diff
        # permanently non-empty, and make the importer's log claim a
        # library is losing comics it still has.
        data.deleted -= ref.missing

        # Before anything reads ``deleted`` — move detection included.
        self.withheld_deleted = self._withhold_unreadable(data, snapshot)

        self._find_moved_paths(data)
        self._find_modified_paths(data, force=force)

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
        self.revived: tuple[RevivedPath, ...] = self._find_revived(ref, snapshot)

    @staticmethod
    def _find_revived(ref: Snapshot, snapshot: Snapshot) -> tuple[RevivedPath, ...]:
        """
        Stamped rows whose paths are back on disk.

        This set exists because a revival generates no event of its own.
        The stamped path is in ``ref.paths`` (the row was kept) and in
        ``snapshot.paths`` (the file is back), so it is neither added nor
        deleted; it falls through to ``_find_modified_paths``, which
        compares stats. **A revival whose stat is unchanged -- a
        remount, a share that reconnected, an unmount/mount cycle, which
        is the exact scenario retention exists for -- produces no diff
        entry at all**, and the poll returns "Nothing changed".

        A second layer would block it even if an event did arrive: the
        importer's read phase skips a path whose on-disk stat equals the
        stored one, so it never enters CREATE_COMICS or UPDATE_COMICS.
        Hooking revival into the import path is therefore not sufficient
        either, which is why this is a poller-side pass.

        Without it the row stays hidden until the reaper hard-deletes
        it, and the *next* poll sees the path as ``added`` and imports it
        as a fresh comic with no bookmarks -- the original bug, delayed
        by a day and now silent.
        """
        revived = []
        for path in sorted(ref.missing & snapshot.paths):
            model = ref.model_for_path(path)
            if model is None:
                continue
            revived.append(RevivedPath(path=path, model=model))
        return tuple(revived)

    @staticmethod
    def _withhold_unreadable(data: _DiffData, snapshot: Snapshot) -> frozenset[str]:
        """
        Keep paths the walk could not read out of ``deleted``.

        A path missing from a disk snapshot usually means the file is
        gone. Under an unreadable directory it means nothing at all —
        the walk never got to look. Deleting those rows cascades the
        comics' bookmarks away and the next healthy poll re-imports the
        files as fresh, unread comics, which is unrecoverable.

        Both failure routes are covered. A directory whose ``scandir``
        failed is itself still in ``paths`` (its parent stat'd it), so
        only its descendants need withholding; an entry whose own
        ``stat`` failed is absent too, so the path must match by
        equality as well as by prefix. The separator guard stops
        ``/c/Pub`` from claiming ``/c/Pub Two``.

        Withholding is not deferral of a real delete: the row still
        points at a path the scanner could not see, and the next poll
        that can read it reconciles normally.

        A withheld path can still be claimed as a *move* source by an
        added file carrying its inode — a comic carried out of the
        unreadable directory. That is deliberate: moving the row keeps
        the bookmarks with the file, where refusing the pair would mint
        a second row and leave the first to be deleted once the
        directory reads again.
        """
        unreadable = snapshot.unreadable
        if not unreadable:
            return frozenset()
        prefixes = tuple(path.rstrip(os.sep) + os.sep for path in unreadable)
        withheld = frozenset(
            path
            for path in data.deleted
            if path in unreadable or path.startswith(prefixes)
        )
        if withheld:
            data.deleted -= withheld
            reason = (
                f"Not deleting {len(withheld)} paths under"
                f" {len(unreadable)} unreadable directories. They will be"
                " reconciled when the directories can be read again."
            )
            snapshot.log.warning(reason)
        return withheld

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

        A pair refused here is not lost: ``_pair_by_signature`` gets a
        second look at it with evidence that does not depend on the
        inode being meaningful.
        """
        src_is_dir = data.ref.is_dir(src)
        if src_is_dir != data.snapshot.is_dir(dest):
            return False
        return src_is_dir or data.ref.size(src) == data.snapshot.size(dest)

    def _find_moved_paths(self, data: _DiffData) -> None:
        """
        Detect moves by matching inodes between deleted and added sets.

        A move pair is only inferred when the inode uniquely identifies a
        path on *both* sides. An inode that maps to more than one path
        within a snapshot (a collision under ``_ignore_device`` or after
        an inode-space rotation) is skipped on the source side and resolves
        to ``None`` on the target side — safe against the wrong-folder
        reparenting that a bogus pair caused.

        Everything still unpaired afterwards goes to
        ``_pair_by_signature``, which is the tier that catches a move
        whose inode changed.
        """
        for old_path in tuple(data.deleted):
            inode = data.ref.inode(old_path)
            if data.ref.is_ambiguous_inode(inode):
                continue
            new_path = data.snapshot.path(inode)
            if new_path and self._is_move_compatible(data, old_path, new_path):
                data.deleted.remove(old_path)
                data.moved.add((old_path, new_path))

        for new_path in tuple(data.added):
            inode = data.snapshot.inode(new_path)
            if data.snapshot.is_ambiguous_inode(inode):
                continue
            old_path = data.ref.path(inode)
            if old_path and self._is_move_compatible(data, old_path, new_path):
                data.added.remove(new_path)
                data.moved.add((old_path, new_path))

        self._pair_by_signature(data)

    @staticmethod
    def _signature(snap: Snapshot, path: str) -> tuple[str, int, float]:
        """Identify a file by what survives a move that loses the inode."""
        return (PurePath(path).name, snap.size(path), snap.mtime(path))

    @classmethod
    def _unique_file_signatures(
        cls, snap: Snapshot, paths: Collection[str]
    ) -> dict[tuple[str, int, float], str]:
        """
        Map signature to path, for files whose signature is unique here.

        A signature shared by two paths on either side identifies
        neither, so both are dropped rather than guessed at.
        """
        seen: dict[tuple[str, int, float], str | None] = {}
        for path in paths:
            if snap.is_dir(path):
                continue
            signature = cls._signature(snap, path)
            seen[signature] = None if signature in seen else path
        return {sig: path for sig, path in seen.items() if path is not None}

    @classmethod
    def _pair_by_signature(cls, data: _DiffData) -> None:
        """
        Pair leftover deletes and adds by name, size and mtime.

        An inode is identity, so it pairs a move outright. But a move
        does not always keep one: a copy-then-delete, a cross-device
        ``mv``, or a remount that rotated the inode space all present as
        a delete plus an add. Left there, the delete cascades the comic's
        bookmarks away and the add re-imports the same file as a fresh,
        unread comic — and the existence backstop cannot help, because
        the old path really is gone.

        Name, size and mtime together are weak evidence next to an
        inode, so the tier only fires when the signature is unique on
        *both* sides, which makes a wrong pair impossible by
        construction rather than unlikely. The filename carries most of
        that weight: a bulk copy hands many files the same size and
        mtime, and without the name they would pair with each other.

        The cost of keeping the name is that this pairs a file that
        **moved**, not one renamed to a different name. A new-inode
        rename has nothing left to match on and is still a delete plus
        an add.

        Files only: a directory's size is meaningless and its mtime
        moves with any child change. Children pair one at a time, the
        importer creates the destination folders, and the old folder row
        deletes normally — folders hold no bookmarks.

        mtime compares exactly, as ``_is_stats_equal`` does. A
        filesystem that truncates it across a copy (FAT, some SMB) will
        not pair, and falls back to today's delete-plus-add.
        """
        old_by_signature = cls._unique_file_signatures(data.ref, data.deleted)
        if not old_by_signature:
            return
        new_by_signature = cls._unique_file_signatures(data.snapshot, data.added)
        paired = 0
        for signature, old_path in old_by_signature.items():
            new_path = new_by_signature.get(signature)
            if new_path is None:
                continue
            data.deleted.remove(old_path)
            data.added.remove(new_path)
            data.moved.add((old_path, new_path))
            data.snapshot.log.debug(
                f"Paired move by name, size and mtime: {old_path} -> {new_path}"
            )
            paired += 1
        if paired:
            data.snapshot.log.info(f"Paired {paired} moves by name, size and mtime.")

    def _find_modified_paths(self, data: _DiffData, *, force: bool) -> None:
        """
        Find paths with changed stats (mtime/size).

        ``force`` skips the comparison and calls everything modified.
        That used to be arranged upstream, by zeroing every mtime in
        the database snapshot — but move detection reads the same
        snapshot, and a zeroed mtime matches no signature, so a forced
        poll could not pair an inode-losing move at all. Deciding it
        here leaves the snapshot honest for ``_find_moved_paths``.

        Moves are included: a forced poll re-reads the destination,
        which is where the content now lives.
        """
        for path in data.unchanged:
            if force or not self._is_stats_equal(data, path, path):
                data.modified.add(path)

        for old_path, new_path in data.moved:
            if force or not self._is_stats_equal(data, old_path, new_path):
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
