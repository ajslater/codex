"""Test the snapshot diff move-detection guards."""

import os
from logging import getLogger

from codex.librarian.fs.poller.snapshot import Snapshot
from codex.librarian.fs.poller.snapshot_diff import SnapshotDiff
from codex.models import Comic, Folder

# os.stat_result tuple positions: mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime
_DIR_MODE = 0o040755  # drwxr-xr-x
_FILE_MODE = 0o100644  # -rw-r--r--


def _stat(*, mode: int, ino: int, size: int, mtime: float = 1.0) -> os.stat_result:
    return os.stat_result((mode, ino, 0, 0, 0, 0, size, 0, mtime, 0))


def _snapshot(
    entries: dict[str, os.stat_result],
    *,
    models: dict[str, type] | None = None,
) -> Snapshot:
    """Build a Snapshot directly from a path→stat map, bypassing disk/db."""
    snap = Snapshot.__new__(Snapshot)
    snap._root = "/comics"  # noqa: SLF001
    snap.log = getLogger("test")
    snap._covers_only = False  # noqa: SLF001
    snap._ignore_device = True  # noqa: SLF001
    snap._stat_info = dict(entries)  # noqa: SLF001
    snap._device_inode_to_path = {  # noqa: SLF001
        (0, st.st_ino): path for path, st in entries.items()
    }
    snap._path_to_model = dict(models) if models else {}  # noqa: SLF001
    return snap


def test_real_file_rename_is_detected() -> None:
    """Sanity: a legitimate file move (same inode, same size) is still a move."""
    db = _snapshot(
        {
            "/comics/a.cbz": _stat(mode=_FILE_MODE, ino=42, size=1000),
        }
    )
    disk = _snapshot(
        {
            "/comics/b.cbz": _stat(mode=_FILE_MODE, ino=42, size=1000),
        }
    )
    diff = SnapshotDiff(db, disk)
    assert diff.files_moved == [("/comics/a.cbz", "/comics/b.cbz")]
    assert not diff.files_deleted
    assert not diff.files_added


def test_real_directory_rename_is_detected() -> None:
    """Sanity: a directory rename (same inode, type both dir) is a move."""
    db = _snapshot(
        {
            "/comics/Old": _stat(mode=_DIR_MODE, ino=99, size=128),
        }
    )
    disk = _snapshot(
        {
            "/comics/New": _stat(mode=_DIR_MODE, ino=99, size=200),  # size differs
        }
    )
    diff = SnapshotDiff(db, disk)
    # Directory moves don't require size match because dir st_size
    # varies with entry count.
    assert diff.dirs_moved == [("/comics/Old", "/comics/New")]


def test_file_to_directory_inode_collision_is_not_a_move() -> None:
    """A file in DB and a dir on disk sharing an inode must not be paired."""
    db = _snapshot(
        {
            "/comics/Powers Gods #001.cbz": _stat(
                mode=_FILE_MODE, ino=1104, size=220_000_000
            ),
        }
    )
    disk = _snapshot(
        {
            "/comics/Wolverine Saga (1989)": _stat(mode=_DIR_MODE, ino=1104, size=224),
        }
    )
    diff = SnapshotDiff(db, disk)
    # The file is gone, the directory is new — no phantom rename.
    assert not diff.files_moved
    assert not diff.dirs_moved
    assert diff.files_deleted == ["/comics/Powers Gods #001.cbz"]
    assert diff.dirs_added == ["/comics/Wolverine Saga (1989)"]


def test_directory_to_file_inode_collision_is_not_a_move() -> None:
    """A dir in DB and a file on disk sharing an inode must not be paired."""
    db = _snapshot(
        {
            "/comics/Old Folder": _stat(mode=_DIR_MODE, ino=77, size=128),
        }
    )
    disk = _snapshot(
        {
            "/comics/some.cbz": _stat(mode=_FILE_MODE, ino=77, size=50_000),
        }
    )
    diff = SnapshotDiff(db, disk)
    assert not diff.dirs_moved
    assert not diff.files_moved
    assert diff.dirs_deleted == ["/comics/Old Folder"]
    assert diff.files_added == ["/comics/some.cbz"]


def test_file_to_file_size_mismatch_is_not_a_move() -> None:
    """Two unrelated files sharing an inode but with different sizes don't pair."""
    db = _snapshot(
        {
            "/comics/a.cbz": _stat(mode=_FILE_MODE, ino=200, size=100),
        }
    )
    disk = _snapshot(
        {
            "/comics/b.cbz": _stat(mode=_FILE_MODE, ino=200, size=999),
        }
    )
    diff = SnapshotDiff(db, disk)
    assert not diff.files_moved
    assert diff.files_deleted == ["/comics/a.cbz"]
    assert diff.files_added == ["/comics/b.cbz"]


def test_unchanged_paths_are_unaffected_by_guards() -> None:
    """Paths present in both snapshots must not become spurious moves."""
    stat = _stat(mode=_FILE_MODE, ino=5, size=1000)
    db = _snapshot({"/comics/a.cbz": stat})
    disk = _snapshot({"/comics/a.cbz": stat})
    diff = SnapshotDiff(db, disk)
    assert diff.is_empty()


def test_stale_stat_refresh_emitted_for_inode_rotation_only() -> None:
    """Path with same content but different inode → queue a stat refresh."""
    fresh_ino = 999
    db = _snapshot(
        {
            "/comics/a.cbz": _stat(mode=_FILE_MODE, ino=100, size=1000),
            "/comics/b.cbz": _stat(mode=_FILE_MODE, ino=200, size=2000),
        },
        models={"/comics/a.cbz": Comic, "/comics/b.cbz": Comic},
    )
    disk = _snapshot(
        {
            # a.cbz: same mtime+size, fresh inode (Docker-remount fingerprint)
            "/comics/a.cbz": _stat(mode=_FILE_MODE, ino=fresh_ino, size=1000),
            # b.cbz: identical to DB, no refresh needed
            "/comics/b.cbz": _stat(mode=_FILE_MODE, ino=200, size=2000),
        },
    )
    diff = SnapshotDiff(db, disk)
    refreshes = diff.stale_stat_refreshes
    assert len(refreshes) == 1
    assert refreshes[0].path == "/comics/a.cbz"
    assert refreshes[0].model is Comic
    assert refreshes[0].disk_stat.st_ino == fresh_ino
    # The path is still "unchanged" — no diff event fires for it.
    assert not diff.files_modified
    assert not diff.files_moved


def test_stale_stat_refresh_skipped_when_content_changed() -> None:
    """If mtime or size differs, the path is modified — not stale-stat."""
    db = _snapshot(
        {"/comics/a.cbz": _stat(mode=_FILE_MODE, ino=100, size=1000, mtime=1.0)},
        models={"/comics/a.cbz": Comic},
    )
    disk = _snapshot(
        {
            # mtime changed → real modification, not just a stale stat
            "/comics/a.cbz": _stat(mode=_FILE_MODE, ino=999, size=1000, mtime=2.0)
        }
    )
    diff = SnapshotDiff(db, disk)
    assert diff.stale_stat_refreshes == ()
    assert diff.files_modified == ["/comics/a.cbz"]


def test_stale_stat_refresh_handles_folder_paths() -> None:
    """Inode rotation on a directory path also queues a refresh."""
    db = _snapshot(
        {"/comics/Some Series": _stat(mode=_DIR_MODE, ino=50, size=128)},
        models={"/comics/Some Series": Folder},
    )
    disk = _snapshot(
        {"/comics/Some Series": _stat(mode=_DIR_MODE, ino=777, size=128)},
    )
    diff = SnapshotDiff(db, disk)
    assert len(diff.stale_stat_refreshes) == 1
    assert diff.stale_stat_refreshes[0].model is Folder


def test_stale_stat_refresh_skips_paths_without_model() -> None:
    """Library root has no DB row; never emit a refresh for it."""
    db = _snapshot(
        # No model entry for the bare root; DatabaseSnapshot adds the
        # root via Path.stat(), not the per-model walk.
        {"/comics": _stat(mode=_DIR_MODE, ino=1, size=128)},
        models={},
    )
    disk = _snapshot(
        {"/comics": _stat(mode=_DIR_MODE, ino=2, size=128)},
    )
    diff = SnapshotDiff(db, disk)
    assert diff.stale_stat_refreshes == ()


def test_stale_stat_refresh_empty_when_inodes_match() -> None:
    """No drift, no refreshes — the common case."""
    stat = _stat(mode=_FILE_MODE, ino=42, size=1000)
    db = _snapshot({"/comics/a.cbz": stat}, models={"/comics/a.cbz": Comic})
    disk = _snapshot({"/comics/a.cbz": stat})
    diff = SnapshotDiff(db, disk)
    assert diff.stale_stat_refreshes == ()
