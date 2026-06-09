"""Filesystem and database snapshot classes for change detection."""

import os
from collections.abc import Iterator
from pathlib import Path
from stat import S_ISDIR

from django.db.models import Model

from codex.librarian.fs.filters import is_ignored_basename, match_comic
from codex.models import Comic, FailedImport, Folder

IGNORE_ST_DEV = 0


class Snapshot:
    """Base snapshot: a mapping of paths to stat results."""

    def __init__(self, root: str, logger_, *, ignore_device: bool = True) -> None:
        """Initialize empty snapshot."""
        self._root = root
        self.log = logger_
        self._ignore_device = ignore_device
        self._stat_info: dict[str, os.stat_result] = {}
        self._device_inode_to_path: dict[tuple[int, int], str] = {}
        # Inodes seen on more than one path within this snapshot. With
        # ``_ignore_device=True`` (Docker/multi-mount) or after a remount
        # rotates the kernel's inode space, an inode key is no longer a
        # unique file identity, so it must NOT drive move detection — a
        # collided inode could otherwise pair an unrelated delete/add and
        # let the importer reparent comics under the wrong folder. ``path``
        # returns ``None`` for these so such pairs degrade to delete+add.
        self._ambiguous_inodes: set[tuple[int, int]] = set()
        # ``DatabaseSnapshot`` populates this with the source model for
        # each path so the poller can refresh stale stats by model.
        # ``DiskSnapshot`` leaves it empty.
        self._path_to_model: dict[str, type[Model]] = {}

    def _inode(self, st: os.stat_result) -> tuple[int, int]:
        """Build a device:inode Key."""
        st_dev = IGNORE_ST_DEV if self._ignore_device else st.st_dev
        return (st_dev, st.st_ino)

    def _set_lookups(self, path: str, st: os.stat_result) -> None:
        """Populate the lookup dicts for a single path."""
        self._stat_info[path] = st
        inode_key = self._inode(st)
        existing = self._device_inode_to_path.get(inode_key)
        if existing is not None and existing != path:
            # Collision: this inode now maps to two distinct paths. Flag it
            # so ``path`` refuses to use it for move matching.
            self._ambiguous_inodes.add(inode_key)
        self._device_inode_to_path[inode_key] = path

    @property
    def paths(self) -> frozenset[str]:
        """All known paths."""
        return frozenset(self._stat_info.keys())

    def inode(self, path: str) -> tuple[int, int]:
        """Return (device, inode) for a path."""
        st = self._stat_info[path]
        return self._inode(st)

    def path(self, st_lookup: tuple[int, int]) -> str | None:
        """Return the path for a device, inode pair, or None if ambiguous."""
        if st_lookup in self._ambiguous_inodes:
            # An inode shared by multiple paths can't identify a unique
            # rename target; suppress the match so the diff falls back to
            # delete+add rather than risking a wrong-folder reparent.
            return None
        return self._device_inode_to_path.get(st_lookup)

    def is_ambiguous_inode(self, st_lookup: tuple[int, int]) -> bool:
        """Return whether this inode maps to more than one path here."""
        return st_lookup in self._ambiguous_inodes

    def mtime(self, path: str) -> float:
        """Return mtime for a path."""
        return self._stat_info[path].st_mtime

    def size(self, path: str) -> int:
        """Return size for a path."""
        return self._stat_info[path].st_size

    def is_dir(self, path: str) -> bool:
        """Return whether path is a directory."""
        return S_ISDIR(self._stat_info[path].st_mode)

    def is_cover(self, path: str) -> bool:  # noqa: ARG002
        """Covers no longer live inside libraries; always False."""
        return False

    def stat(self, path: str) -> os.stat_result:
        """Return the raw stat for a path."""
        return self._stat_info[path]

    def model_for_path(self, path: str) -> type[Model] | None:
        """
        Return the source model for a DB-snapshot path, or None.

        Only meaningful on ``DatabaseSnapshot``. Used by Phase-3 stale-
        stat refresh to bulk-update each affected row by its native
        model.
        """
        return self._path_to_model.get(path)


class DiskSnapshot(Snapshot):
    """Snapshot of the filesystem taken by walking a directory tree."""

    def __init__(
        self,
        root: str,
        logger_,
        *,
        recursive: bool = True,
        follow_symlinks: bool = True,
        ignore_device: bool = True,
    ) -> None:
        """Walk the directory and stat every entry."""
        super().__init__(root, logger_, ignore_device=ignore_device)
        self._recursive = recursive
        self._follow_symlinks = follow_symlinks
        self._init_walk()

    def _init_walk(self):
        """Walk disk fs tree."""
        root_stat = Path(self._root).stat()
        self._set_lookups(self._root, root_stat)
        self._walk(self._root)

    def _should_include(self, path: Path, *, is_dir: bool) -> bool:
        """Decide whether a scanned entry belongs in the snapshot."""
        if is_dir:
            return self._recursive
        return match_comic(path)

    def _walk(self, root: str) -> None:
        """Walk the directory tree and populate lookups."""
        for entry in os.scandir(root):
            # Walking only the surviving children means the recursion
            # never enters an ignored dir (``.git`` / ``.Trashes`` /
            # ``@eaDir`` if registered / …), so a per-component check
            # at each scandir level suffices — no need to re-check
            # ancestors. See ``filters._IGNORED_BASENAMES`` /
            # ``_IGNORED_BASENAME_PREFIXES`` for the registered rules.
            if is_ignored_basename(entry.name):
                continue
            is_dir = entry.is_dir(follow_symlinks=self._follow_symlinks)
            if not self._should_include(Path(entry.path), is_dir=is_dir):
                continue
            try:
                st = entry.stat(follow_symlinks=self._follow_symlinks)
            except OSError:
                continue
            self._set_lookups(entry.path, st)
            if is_dir:
                self._walk(entry.path)


class DatabaseSnapshot(Snapshot):
    """Snapshot of what the Codex database knows about a library's files."""

    _MODELS = (Folder, Comic, FailedImport)
    _STAT_LEN = 10

    def __init__(
        self,
        root: str,
        logger_,
        *,
        ignore_device: bool = True,
        force: bool = False,
    ) -> None:
        """Build snapshot from database records for the given library root."""
        super().__init__(root, logger_, ignore_device=ignore_device)
        self._force = force
        self._init_walk()

    def _init_walk(self):
        """Walk database fs tree."""
        root_path = Path(self._root)
        if not root_path.is_dir():
            self.log.warning(f"{self._root} not found, cannot snapshot.")
            return

        # Add the library root itself
        root_stat = root_path.stat()
        self._set_lookups(self._root, root_stat)

        for model, wp in self._walk(self._root, self._MODELS):
            st = self._create_stat(wp, force=self._force)
            self._set_lookups(wp["path"], st)
            # Track which model owns each path so the poller's stale-
            # stat refresh can bulk-update by model. Model order in
            # ``_MODELS`` puts ``Comic`` after ``Folder``, so on the
            # rare path collision the comic-owned mapping wins —
            # matches the legacy ``_set_lookups`` overwrite behavior.
            self._path_to_model[wp["path"]] = model

    @staticmethod
    def _walk(root: str, models: tuple) -> Iterator[tuple[type[Model], dict]]:
        """Yield (model, {path, stat} dict) for every row across all models."""
        for model in models:
            qs = (
                model.objects.filter(library__path=root)
                .order_by("path")
                .values("path", "stat")
            )
            for wp in qs:
                yield model, wp

    def _create_stat(self, wp: dict, *, force: bool) -> os.stat_result:
        """Turn a database JSON stat array into an os.stat_result."""
        stat = wp["stat"]
        if not stat or len(stat) != self._STAT_LEN:
            path = Path(wp["path"])
            if path.exists():
                self.log.debug(f"Force modify path with missing db stat: {path}")
                stat = list(path.stat())
                stat[8] = 0.0  # Fake mtime triggers modified event
            else:
                self.log.debug(
                    f"Force delete missing path with missing db stat: {path}"
                )
                stat = list(Comic.ZERO_STAT)

        if force:
            stat = list(stat)
            stat[8] = 0.0  # Fake mtime triggers modified event

        return os.stat_result(tuple(stat))
