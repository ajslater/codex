"""Test the snapshot diff move-detection guards."""

import os
from logging import getLogger
from types import MappingProxyType
from unittest.mock import MagicMock

from django.db.models import Model

from codex.librarian.fs.poller.snapshot import Snapshot
from codex.librarian.fs.poller.snapshot_diff import SnapshotDiff
from codex.models import Comic, Folder

# os.stat_result tuple positions: mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime
_DIR_MODE = 0o040755  # drwxr-xr-x
#: Comics in ``TestWithholdUnreadable._DB`` that a healthy walk deletes.
_DEAD_COMICS = 3
_FILE_MODE = 0o100644  # -rw-r--r--


def _stat(*, mode: int, ino: int, size: int, mtime: float = 1.0) -> os.stat_result:
    return os.stat_result((mode, ino, 0, 0, 0, 0, size, 0, mtime, 0))


def _snapshot(
    entries: dict[str, os.stat_result],
    *,
    models: dict[str, type[Model]] | None = None,
    unreadable: set[str] | None = None,
    log=None,
) -> Snapshot:
    """
    Build a Snapshot from a path→stat map, bypassing disk/db.

    Drives the real ``_set_lookups`` so intra-snapshot inode collisions
    populate ``_ambiguous_inodes`` exactly as production would.
    """
    snap = Snapshot.__new__(Snapshot)
    snap._root = "/comics"  # noqa: SLF001
    snap.log = log or getLogger("test")
    snap._ignore_device = True  # noqa: SLF001
    snap._stat_info = {}  # noqa: SLF001
    snap._device_inode_to_path = {}  # noqa: SLF001
    snap._ambiguous_inodes = set()  # noqa: SLF001
    snap._path_to_model = dict(models) if models else {}  # noqa: SLF001
    snap._unreadable = set(unreadable) if unreadable else set()  # noqa: SLF001
    for path, st in entries.items():
        snap._set_lookups(path, st)  # noqa: SLF001
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


def test_intra_snapshot_file_inode_collision_suppresses_move() -> None:
    """
    Two disk files sharing one inode can't be a unique rename target.

    Regression: with ``_ignore_device`` (or after an inode-space
    rotation), a single inode can map to several paths. The old
    last-write-wins lookup would pair the deleted file with whichever
    colliding path happened to be stored, fabricating a move. The
    ambiguity guard must instead degrade to delete+add.
    """
    db = _snapshot({"/comics/a.cbz": _stat(mode=_FILE_MODE, ino=42, size=1000)})
    disk = _snapshot(
        {
            "/comics/b.cbz": _stat(mode=_FILE_MODE, ino=42, size=1000),
            "/comics/c.cbz": _stat(mode=_FILE_MODE, ino=42, size=1000),
        }
    )
    diff = SnapshotDiff(db, disk)
    assert not diff.files_moved
    assert diff.files_deleted == ["/comics/a.cbz"]
    assert sorted(diff.files_added) == ["/comics/b.cbz", "/comics/c.cbz"]


def test_intra_snapshot_dir_inode_collision_suppresses_move() -> None:
    """
    Two disk dirs sharing one inode must not pair (the wrong-folder trigger).

    Directory pairs skip the size check, so without the ambiguity guard a
    collided inode would reparent comics under an unrelated folder.
    """
    db = _snapshot({"/comics/Punisher": _stat(mode=_DIR_MODE, ino=50, size=128)})
    disk = _snapshot(
        {
            "/comics/Wolverine": _stat(mode=_DIR_MODE, ino=50, size=128),
            "/comics/Akira": _stat(mode=_DIR_MODE, ino=50, size=96),
        }
    )
    diff = SnapshotDiff(db, disk)
    assert not diff.dirs_moved
    assert diff.dirs_deleted == ["/comics/Punisher"]
    assert sorted(diff.dirs_added) == ["/comics/Akira", "/comics/Wolverine"]


def test_db_side_inode_collision_suppresses_move() -> None:
    """Ambiguity on the reference (DB) side also suppresses a move pair."""
    db = _snapshot(
        {
            "/comics/a.cbz": _stat(mode=_FILE_MODE, ino=7, size=1000),
            "/comics/b.cbz": _stat(mode=_FILE_MODE, ino=7, size=1000),
        }
    )
    disk = _snapshot({"/comics/c.cbz": _stat(mode=_FILE_MODE, ino=7, size=1000)})
    diff = SnapshotDiff(db, disk)
    assert not diff.files_moved
    assert sorted(diff.files_deleted) == ["/comics/a.cbz", "/comics/b.cbz"]
    assert diff.files_added == ["/comics/c.cbz"]


class TestWithholdUnreadable:
    """Deletes under a path the walk could not read are withheld."""

    _DB = MappingProxyType(
        {
            "/comics/Pub": _stat(mode=_DIR_MODE, ino=1, size=128),
            "/comics/Pub/a.cbz": _stat(mode=_FILE_MODE, ino=2, size=100),
            "/comics/Pub/Sub": _stat(mode=_DIR_MODE, ino=3, size=128),
            "/comics/Pub/Sub/b.cbz": _stat(mode=_FILE_MODE, ino=4, size=100),
            "/comics/Pub Two/c.cbz": _stat(mode=_FILE_MODE, ino=5, size=100),
        }
    )

    def test_unreadable_subtree_is_not_deleted(self) -> None:
        """The reporter's incident: one unreadable publisher directory."""
        db = _snapshot(dict(self._DB))
        # The scandir route: the directory itself stat'd, its children
        # never listed. Everything outside it is healthy.
        disk = _snapshot(
            {
                "/comics/Pub": self._DB["/comics/Pub"],
                "/comics/Pub Two/c.cbz": self._DB["/comics/Pub Two/c.cbz"],
            },
            unreadable={"/comics/Pub"},
        )

        diff = SnapshotDiff(db, disk)

        assert not diff.files_deleted
        assert not diff.dirs_deleted
        assert diff.withheld_deleted == {
            "/comics/Pub/a.cbz",
            "/comics/Pub/Sub",
            "/comics/Pub/Sub/b.cbz",
        }

    def test_a_real_delete_elsewhere_still_lands(self) -> None:
        """Withholding is per subtree, not a poll-wide refusal."""
        db = _snapshot(dict(self._DB))
        disk = _snapshot(
            {"/comics/Pub": self._DB["/comics/Pub"]},
            unreadable={"/comics/Pub"},
        )

        diff = SnapshotDiff(db, disk)

        # The comic outside the unreadable subtree really is gone.
        assert diff.files_deleted == ["/comics/Pub Two/c.cbz"]

    def test_sibling_prefix_is_not_claimed(self) -> None:
        """``/comics/Pub`` must not withhold ``/comics/Pub Two``."""
        db = _snapshot(dict(self._DB))
        disk = _snapshot({}, unreadable={"/comics/Pub"})

        diff = SnapshotDiff(db, disk)

        assert "/comics/Pub Two/c.cbz" not in diff.withheld_deleted
        assert diff.files_deleted == ["/comics/Pub Two/c.cbz"]

    def test_the_unreadable_path_itself_is_withheld(self) -> None:
        """The per-entry route: the failed entry is absent from the walk too."""
        db = _snapshot(dict(self._DB))
        disk = _snapshot({}, unreadable={"/comics/Pub"})

        diff = SnapshotDiff(db, disk)

        assert "/comics/Pub" not in diff.dirs_deleted
        assert "/comics/Pub" in diff.withheld_deleted

    def test_a_lone_unreadable_file_is_withheld(self) -> None:
        """One comic that would not stat must not lose its bookmarks."""
        db = _snapshot({"/comics/x.cbz": _stat(mode=_FILE_MODE, ino=9, size=1)})
        disk = _snapshot({}, unreadable={"/comics/x.cbz"})

        diff = SnapshotDiff(db, disk)

        assert not diff.files_deleted
        assert diff.withheld_deleted == {"/comics/x.cbz"}

    def test_withholding_is_reported(self) -> None:
        """Silent correctness is how this bug survived; say what was withheld."""
        log = MagicMock()
        db = _snapshot(dict(self._DB))
        disk = _snapshot({}, unreadable={"/comics/Pub"}, log=log)

        SnapshotDiff(db, disk)

        log.warning.assert_called_once()
        assert "Not deleting" in log.warning.call_args[0][0]

    def test_nothing_unreadable_changes_nothing(self) -> None:
        """A healthy walk still deletes what is really gone."""
        log = MagicMock()
        db = _snapshot(dict(self._DB))
        disk = _snapshot({}, log=log)

        diff = SnapshotDiff(db, disk)

        assert not diff.withheld_deleted
        assert len(diff.files_deleted) == _DEAD_COMICS
        assert sorted(diff.dirs_deleted) == ["/comics/Pub", "/comics/Pub/Sub"]
        log.warning.assert_not_called()

    def test_a_move_out_of_an_unreadable_subtree_still_pairs(self) -> None:
        """
        Withholding a delete must not cost a real rename its row.

        A file carried out of the unreadable directory turns up at a new
        path with its inode intact. Pairing it moves the row, which is
        what keeps the bookmarks; refusing the pair would mint a second
        row and leave the first to be deleted once the directory reads
        again — the very loss this withholding exists to prevent.
        """
        db = _snapshot({"/comics/Pub/a.cbz": _stat(mode=_FILE_MODE, ino=2, size=100)})
        disk = _snapshot(
            {"/comics/elsewhere.cbz": _stat(mode=_FILE_MODE, ino=2, size=100)},
            unreadable={"/comics/Pub"},
        )

        diff = SnapshotDiff(db, disk)

        assert diff.files_moved == [("/comics/Pub/a.cbz", "/comics/elsewhere.cbz")]
        assert not diff.files_deleted
        assert not diff.files_added


class TestSignaturePairing:
    """A move that lost its inode still keeps its row."""

    _OLD = "/comics/a.cbz"
    _NEW = "/comics/Sub/a.cbz"

    def test_new_inode_move_pairs_by_signature(self) -> None:
        """The whole point: copy+delete, cross-device mv, rotated inode space."""
        db = _snapshot({self._OLD: _stat(mode=_FILE_MODE, ino=1, size=100)})
        disk = _snapshot({self._NEW: _stat(mode=_FILE_MODE, ino=2, size=100)})

        diff = SnapshotDiff(db, disk)

        assert diff.files_moved == [(self._OLD, self._NEW)]
        assert not diff.files_deleted
        assert not diff.files_added
        # Same size and mtime, so it is not a modification either.
        assert not diff.files_modified

    def test_signature_needs_a_unique_source(self) -> None:
        """Two candidates to move *from* identify neither."""
        db = _snapshot(
            {
                self._OLD: _stat(mode=_FILE_MODE, ino=1, size=100),
                "/comics/Other/a.cbz": _stat(mode=_FILE_MODE, ino=2, size=100),
            }
        )
        disk = _snapshot({self._NEW: _stat(mode=_FILE_MODE, ino=3, size=100)})

        diff = SnapshotDiff(db, disk)

        assert not diff.files_moved
        assert sorted(diff.files_deleted) == ["/comics/Other/a.cbz", self._OLD]
        assert diff.files_added == [self._NEW]

    def test_signature_needs_a_unique_target(self) -> None:
        """Two candidates to move *to* identify neither."""
        db = _snapshot({self._OLD: _stat(mode=_FILE_MODE, ino=1, size=100)})
        disk = _snapshot(
            {
                self._NEW: _stat(mode=_FILE_MODE, ino=2, size=100),
                "/comics/Other/a.cbz": _stat(mode=_FILE_MODE, ino=3, size=100),
            }
        )

        diff = SnapshotDiff(db, disk)

        assert not diff.files_moved
        assert diff.files_deleted == [self._OLD]

    def test_inode_pair_wins_over_signature(self) -> None:
        """Identity beats evidence when both are available."""
        db = _snapshot({self._OLD: _stat(mode=_FILE_MODE, ino=1, size=100)})
        disk = _snapshot(
            {
                # Same inode, different name: the real rename.
                "/comics/b.cbz": _stat(mode=_FILE_MODE, ino=1, size=100),
                # Same signature, different inode: a copy.
                self._NEW: _stat(mode=_FILE_MODE, ino=2, size=100),
            }
        )

        diff = SnapshotDiff(db, disk)

        assert diff.files_moved == [(self._OLD, "/comics/b.cbz")]
        assert diff.files_added == [self._NEW]

    def test_refused_inode_pair_still_pairs_by_signature(self) -> None:
        """An inode collision refused for size can still be resolved by name."""
        db = _snapshot({self._OLD: _stat(mode=_FILE_MODE, ino=200, size=100)})
        disk = _snapshot(
            {
                # Shares the inode but not the size: refused as a pair.
                "/comics/unrelated.cbz": _stat(mode=_FILE_MODE, ino=200, size=999),
                self._NEW: _stat(mode=_FILE_MODE, ino=201, size=100),
            }
        )

        diff = SnapshotDiff(db, disk)

        assert diff.files_moved == [(self._OLD, self._NEW)]
        assert diff.files_added == ["/comics/unrelated.cbz"]

    def test_mtime_drift_is_not_a_signature_match(self) -> None:
        """Weak evidence must stay strict; a rewritten file is not a move."""
        db = _snapshot({self._OLD: _stat(mode=_FILE_MODE, ino=1, size=100, mtime=1.0)})
        disk = _snapshot(
            {self._NEW: _stat(mode=_FILE_MODE, ino=2, size=100, mtime=2.0)}
        )

        diff = SnapshotDiff(db, disk)

        assert not diff.files_moved
        assert diff.files_deleted == [self._OLD]
        assert diff.files_added == [self._NEW]

    def test_directories_are_not_paired_by_signature(self) -> None:
        """Directory size is meaningless and its mtime moves with any child."""
        db = _snapshot({"/comics/Old": _stat(mode=_DIR_MODE, ino=1, size=128)})
        disk = _snapshot({"/comics/Sub/Old": _stat(mode=_DIR_MODE, ino=2, size=128)})

        diff = SnapshotDiff(db, disk)

        assert not diff.dirs_moved
        assert diff.dirs_deleted == ["/comics/Old"]

    def test_withheld_paths_are_not_signature_sources(self) -> None:
        """
        An unreadable path is not evidence of anything.

        An inode may still pair one, because an inode is identity. A
        signature is only a guess, and the withheld subtree may simply
        come back.
        """
        db = _snapshot({"/comics/Pub/a.cbz": _stat(mode=_FILE_MODE, ino=1, size=100)})
        disk = _snapshot(
            {"/comics/elsewhere/a.cbz": _stat(mode=_FILE_MODE, ino=2, size=100)},
            unreadable={"/comics/Pub"},
        )

        diff = SnapshotDiff(db, disk)

        assert not diff.files_moved
        assert not diff.files_deleted
        assert diff.files_added == ["/comics/elsewhere/a.cbz"]

    def test_signature_pairs_are_logged(self) -> None:
        """A pair made on evidence rather than identity is worth saying."""
        log = MagicMock()
        db = _snapshot({self._OLD: _stat(mode=_FILE_MODE, ino=1, size=100)})
        disk = _snapshot({self._NEW: _stat(mode=_FILE_MODE, ino=2, size=100)}, log=log)

        SnapshotDiff(db, disk)

        log.info.assert_called_once()
        assert "Paired 1 moves" in log.info.call_args[0][0]
        log.debug.assert_called_once()
