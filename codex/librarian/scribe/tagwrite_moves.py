"""
Paths a tag-write batch has moved but has not yet reconciled in the database.

Writing tags can move a comic's archive out from under its database row.
Comicbox repacks an unwritable CBR as a CBZ — a new inode at a new path —
and the rename pass then gives the result its scheme name. ``TagWriter``
records those moves as one targeted ``ImportTask`` enqueued when the whole
batch finishes, but the batch can run for minutes and both scanners report
the same filesystem churn in the meantime.

A watcher batch force-yielded mid-write (60s of continuous activity, see
``codex.librarian.fs.watcher.watcher``) or a poll that lands during the
write carries a conversion as an unrelated delete plus create: the new
archive is a new inode, so neither scanner can pair it into a move. That
task is enqueued *before* the tag writer's, and ``ScribeThread``'s
``PriorityQueue`` breaks ties between equal-priority import tasks by
enqueue time, so it runs first — deleting the comic row by its now-dead
path, cascading its bookmarks away, and leaving the tag writer's move with
no source row to find.

This registry lets the importer recognize those paths as codex's own
in-flight work and leave them to it. ``TagWriter`` registers every path a
move it is about to enqueue passes through; ``init_apply`` drops
registered paths from a task's created/modified/deleted sets and releases
a move's whole group when a task actually carries that move — which the
tag writer's own task does, in the phase that runs before its own reads
and deletes.

The store is process-local on purpose. Only ``ScribeThread`` writes and
reads it, and its lifetime should match the librarian queue's: a librarian
restart loses the pending ``ImportTask`` along with the queue, so a guard
that outlived it would strand those paths instead. The TTL is a backstop
for a batch whose move task never arrives at all; expiry simply restores
the unguarded behavior, which the next scan reconciles.
"""

from __future__ import annotations

from threading import Lock
from time import monotonic
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

# Long enough to outlast a queue backed up behind a large import, short
# enough that a leaked entry heals the same day.
_TTL = 60 * 60 * 6

_LOCK = Lock()
# Guarded path -> (move source, move destination, expiry). Absolute paths
# are unique across libraries — the admin serializer rejects a library
# path that nests inside another — so no library scoping is needed here.
_PENDING: dict[str, tuple[str, str, float]] = {}


def _prune(now: float) -> None:
    """Drop expired entries. Call with the lock held."""
    expired = [path for path, entry in _PENDING.items() if entry[-1] <= now]
    for path in expired:
        del _PENDING[path]


def register_tag_write_move(
    src_path: str, dest_path: str, waypoints: Iterable[str] = ()
) -> None:
    """Guard every path one pending tag-write move passes through."""
    now = monotonic()
    expiry = now + _TTL
    with _LOCK:
        _prune(now)
        for path in (src_path, dest_path, *waypoints):
            _PENDING[path] = (src_path, dest_path, expiry)


def get_pending_tag_write_paths() -> frozenset[str]:
    """Return every path guarded by an unreconciled tag-write move."""
    now = monotonic()
    with _LOCK:
        _prune(now)
        return frozenset(_PENDING)


def release_tag_write_moves(moves: Mapping[str, str]) -> None:
    """
    Release the guarded group of every registered move a task carries.

    Matches on the whole move, not just its source: a scanner that infers
    some *other* destination for a guarded source has not reconciled this
    move and must not lift its guard.
    """
    if not moves:
        return
    with _LOCK:
        released = [
            path for path, (src, dest, _) in _PENDING.items() if moves.get(src) == dest
        ]
        for path in released:
            del _PENDING[path]


def clear_tag_write_moves() -> None:
    """Drop every guard. For test isolation; the process owns the lifetime."""
    with _LOCK:
        _PENDING.clear()
