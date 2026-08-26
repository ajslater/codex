"""
Test ImportTask assembly from filesystem events.

The interesting case is a write followed by a rename, which every external
tagger (including codex's own) performs: the modify event names the file
before the rename, and the rename lands in the same watch batch as a
delete+add pair that inode-matching turns into a move. If the modify keeps
naming the vanished source path, the importer reads a dead path and files a
failed import instead of picking up the new tags.
"""

from codex.librarian.fs.events import FSChange, FSEvent
from codex.librarian.fs.import_task import build_import_task

_LIBRARY_ID = 1
_OLD = "/comics/Series/Old Name #001.cbz"
_NEW = "/comics/Series/New Name v2017 #001.cbz"
_OTHER = "/comics/Series/Untouched #002.cbz"


def _modified(path: str) -> FSEvent:
    return FSEvent(src_path=path, change=FSChange.modified)


def _moved(src: str, dest: str) -> FSEvent:
    return FSEvent(src_path=src, change=FSChange.moved, dest_path=dest)


def _build(*events: FSEvent):
    return build_import_task(_LIBRARY_ID, events)


def test_modified_source_remapped_to_move_dest():
    """A write-then-rename reads the destination, not the vanished source."""
    task = _build(_modified(_OLD), _moved(_OLD, _NEW))

    assert task
    assert task.files_modified == {_NEW}
    assert task.files_moved == {_OLD: _NEW}
    assert task.files_created == set()


def test_modified_dest_passes_through():
    """The poller emits dest-modified for a move whose stats changed."""
    task = _build(_modified(_NEW), _moved(_OLD, _NEW))

    assert task
    assert task.files_modified == {_NEW}
    assert task.files_moved == {_OLD: _NEW}


def test_modified_unrelated_to_move_untouched():
    """A modified path that takes no part in a move is left alone."""
    task = _build(_modified(_OTHER), _moved(_OLD, _NEW))

    assert task
    assert task.files_modified == {_OTHER}


def test_deleted_wins_over_move_and_modified():
    """A deleted source cancels its move, and the remap cannot revive it."""
    task = _build(
        _modified(_OLD),
        _moved(_OLD, _NEW),
        FSEvent(src_path=_OLD, change=FSChange.deleted),
    )

    assert task
    assert task.files_moved == {}
    assert task.files_modified == set()
    assert task.files_deleted == {_OLD}


def test_added_dest_still_dropped():
    """A move's destination is not also a creation."""
    task = _build(FSEvent(src_path=_NEW, change=FSChange.added), _moved(_OLD, _NEW))

    assert task
    assert task.files_created == set()
    assert task.files_moved == {_OLD: _NEW}


def test_no_work_returns_none():
    """A batch with nothing left to do builds no task."""
    # A directory creation has no ImportTask field; the walk that expands it
    # into child file events is what carries the work.
    task = _build(
        FSEvent(src_path="/comics/Series", change=FSChange.added, is_directory=True)
    )

    assert task is None


def _added(path: str) -> FSEvent:
    return FSEvent(src_path=path, change=FSChange.added)


def _deleted(path: str) -> FSEvent:
    return FSEvent(src_path=path, change=FSChange.deleted)


def test_delete_plus_add_of_one_path_is_a_modify():
    """A file replaced in place must be re-read, not deleted."""
    task = _build(_deleted(_OLD), _added(_OLD))

    assert task
    # Letting the delete win would destroy the row — and its bookmarks —
    # while a file sits at that path.
    assert task.files_deleted == set()
    assert task.files_created == set()
    assert task.files_modified == {_OLD}


def test_replaced_path_survives_alongside_a_real_delete():
    """One path's replacement doesn't rescue another path's real delete."""
    task = _build(_deleted(_OLD), _added(_OLD), _deleted(_OTHER))

    assert task
    assert task.files_modified == {_OLD}
    assert task.files_deleted == {_OTHER}


def test_replaced_path_with_a_modify_event_is_not_duplicated():
    """A batch that also reports the write leaves one modify, not two."""
    task = _build(_deleted(_OLD), _added(_OLD), _modified(_OLD))

    assert task
    assert task.files_modified == {_OLD}
    assert task.files_deleted == set()


def test_replaced_cover_is_a_modify():
    """Custom covers replaced in place are re-read too."""
    cover = "/comics/Series/cover.jpg"
    task = _build(
        FSEvent(src_path=cover, change=FSChange.deleted, is_cover=True),
        FSEvent(src_path=cover, change=FSChange.added, is_cover=True),
    )

    assert task
    assert task.covers_deleted == set()
    assert task.covers_created == set()
    assert task.covers_modified == {cover}
