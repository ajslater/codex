"""
The watcher only pairs a delete+add into a move when it could be a rename.

Stored inodes carry no device, and a bulk CBR->CBZ conversion frees many
inodes while creating many files, so an inode match alone is not proof of
a rename: on an inode-reusing filesystem a new CBZ can be handed the inode
a different comic's CBR just released. ``_is_move_compatible`` (ported
from the poller) makes the match load-bearing only when the file type and
size agree, while still pairing the write-then-rename flow whose stored
size is legitimately stale.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final, override

from django.test import TestCase

from codex.librarian.fs.events import FSChange, FSEvent
from codex.librarian.fs.watcher.data import ChangeBatch
from codex.librarian.fs.watcher.move import detect_moves
from codex.models import (
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)

_TMP_DIR: Final = Path("/tmp/codex.tests.watchermove")  # noqa: S108
_OLD_NAME: Final = "old.cbz"
_NEW_NAME: Final = "new.cbz"


class WatcherMoveDetectTests(TestCase):
    """Inode pairs are only trusted when they could be a rename."""

    @override
    def setUp(self) -> None:
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            path=str(_TMP_DIR), events=True
        )
        publisher = Publisher.objects.create(name="P")
        imprint = Imprint.objects.create(name="I", publisher=publisher)
        series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
        self.tags = {  # pyright: ignore[reportUninitializedInstanceVariable]
            "publisher": publisher,
            "imprint": imprint,
            "series": series,
            "volume": Volume.objects.create(
                name="1", publisher=publisher, imprint=imprint, series=series
            ),
        }

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _make_comic(self, name: str, contents: str) -> Comic:
        """Create a comic whose stored stat reflects its own file."""
        path = _TMP_DIR / name
        path.write_text(contents)
        return Comic.objects.create(
            library=self.library,
            path=str(path),
            issue_number=1,
            name=name,
            size=len(contents),
            file_type="CBZ",
            **self.tags,
        )

    @staticmethod
    def _adopt_inode_of(comic: Comic, path: Path) -> None:
        """Point the comic's stored inode at another file, as reuse would."""
        assert comic.stat is not None
        stat = list(comic.stat)
        stat[1] = path.stat().st_ino
        Comic.objects.filter(pk=comic.pk).update(stat=stat)

    def _batch(self, deleted: str, added: str, *, modified: str = "") -> ChangeBatch:
        batch = ChangeBatch()
        batch.deleted.append(
            (self.library.pk, FSEvent(src_path=deleted, change=FSChange.deleted))
        )
        batch.added.append(
            (self.library.pk, FSEvent(src_path=added, change=FSChange.added))
        )
        if modified:
            batch.modified.append(
                (self.library.pk, FSEvent(src_path=modified, change=FSChange.modified))
            )
        return batch

    def test_real_rename_is_paired(self) -> None:
        """A rename keeps the inode, type and size, so it pairs."""
        comic = self._make_comic(_OLD_NAME, "comic")
        old_path = Path(comic.path)
        new_path = _TMP_DIR / _NEW_NAME
        old_path.rename(new_path)
        batch = self._batch(str(old_path), str(new_path))

        moves = detect_moves(batch)

        assert len(moves) == 1
        _, event = moves[0]
        assert event.src_path == str(old_path)
        assert event.dest_path == str(new_path)
        # Matched events are consumed out of the batch.
        assert not batch.added
        assert not batch.deleted

    def test_reused_inode_with_different_size_is_rejected(self) -> None:
        """A recycled inode on an unrelated file is not a move."""
        comic = self._make_comic(_OLD_NAME, "comic")
        old_path = Path(comic.path)
        # A conversion freed this comic's inode; an unrelated new archive
        # of a different size was handed it.
        other_path = _TMP_DIR / _NEW_NAME
        other_path.write_text("a completely different archive")
        old_path.unlink()
        self._adopt_inode_of(comic, other_path)
        batch = self._batch(str(old_path), str(other_path))

        moves = detect_moves(batch)

        # No pair, and both events survive to be handled as delete + add.
        assert not moves
        assert len(batch.added) == 1
        assert len(batch.deleted) == 1

    def test_written_source_waives_the_size_check(self) -> None:
        """An in-place write before a rename still pairs despite the size."""
        comic = self._make_comic(_OLD_NAME, "comic")
        old_path = Path(comic.path)
        # The tagger rewrote the archive in place — same inode, new size —
        # and then renamed it, all inside one watch batch.
        old_path.write_text("comic with many more tags than before")
        new_path = _TMP_DIR / _NEW_NAME
        old_path.rename(new_path)
        batch = self._batch(str(old_path), str(new_path), modified=str(old_path))

        moves = detect_moves(batch)

        assert len(moves) == 1
        assert moves[0][1].dest_path == str(new_path)

    def test_file_type_mismatch_is_rejected(self) -> None:
        """A comic's inode colliding with a directory is never a move."""
        comic = self._make_comic(_OLD_NAME, "comic")
        old_path = Path(comic.path)
        other_dir = _TMP_DIR / "somedir"
        other_dir.mkdir()
        old_path.unlink()
        self._adopt_inode_of(comic, other_dir)
        batch = self._batch(str(old_path), str(other_dir))

        moves = detect_moves(batch)

        assert not moves
        assert len(batch.deleted) == 1
