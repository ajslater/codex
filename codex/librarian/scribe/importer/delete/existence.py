"""
Confirm a scanner's deletes against the filesystem before acting on them.

Deleting a comic row cascades its bookmarks and read progress away, and
nothing restores them — the next scan re-imports the file as a fresh,
unread comic. So a delete is only safe when the file is really gone.

Both scanners infer deletes rather than observing them, and every inference
they make has failure modes: a watcher batch that reports a delete whose
paired add lands in the *next* batch, a directory expansion that overmatched,
an inode pair the compatibility checks refused. In each case the path is
still on disk, and the delete is wrong.

Probing the path is cheap next to what it protects, and a path that is
genuinely gone answers immediately. A row skipped here is not stranded: it
still points at a real file, so the next scan reconciles it normally — a
stale row costs a re-read, a wrongly deleted one costs the user's place in
the book.

This cannot save a library whose whole mount disappeared, where every path
reads as missing. ``DeletedComicsImporter`` logs that case instead.
"""

from collections.abc import Collection
from pathlib import Path


def split_extant(paths: Collection[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Partition paths into (gone from disk, still on disk)."""
    gone: list[str] = []
    extant: list[str] = []
    for path in paths:
        if Path(path).exists():
            extant.append(path)
        else:
            gone.append(path)
    return tuple(gone), tuple(extant)


def confirm_deleted(paths: Collection[str], log, kind: str) -> tuple[str, ...]:
    """Return only the paths that are really gone, reporting any that aren't."""
    gone, extant = split_extant(paths)
    if extant:
        reason = (
            f"Not deleting {len(extant)} {kind} a scan reported missing that"
            f" are still on disk. The next scan will reconcile them."
        )
        log.warning(reason)
    return gone
