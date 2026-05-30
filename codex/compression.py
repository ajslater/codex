"""
xz (LZMA) helpers for backup artifacts.

Stdlib-only. Backups are streamed straight into ``lzma`` so we never write
an uncompressed intermediate to disk:

* The main DB backup hands :func:`write_xz_bytes` a consistent binary image
  from ``sqlite3.Connection.serialize()``.
* The user-data sidecar streams ``Connection.iterdump()`` SQL text directly
  into an ``lzma`` text stream (see :mod:`codex.user_data.dump`).

Dated nightly backups accumulate under ``BACKUP_DB_DIR``; :func:`prune_dated`
caps each set to :data:`BACKUP_KEEP`.
"""

from __future__ import annotations

import lzma
import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

# ``preset=6`` is the lzma default — a good size/speed balance for a
# background nightly task. Single-threaded; the stdlib has no threaded xz.
PRESET: Final[int] = 6
XZ_SUFFIX: Final[str] = ".xz"
# Most recent dated backups to retain per artifact set.
BACKUP_KEEP: Final[int] = 7


def write_xz_bytes(data: bytes, dest: Path) -> None:
    """
    xz-compress ``data`` to ``dest`` atomically.

    Writes a sibling ``.tmp`` then ``replace()``s it into place so a crash
    mid-compress can't leave a truncated backup at ``dest``. The compressor
    streams to disk, so only ``data`` (the raw image) is held in memory.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with lzma.open(tmp, "wb", preset=PRESET) as out:
            out.write(data)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)


def read_text_maybe_xz(path: Path) -> str:
    """Read ``path`` as text, transparently decompressing an ``.xz`` file."""
    if path.suffix == XZ_SUFFIX:
        with lzma.open(path, "rt", encoding="utf-8") as src:
            return src.read()
    return path.read_text(encoding="utf-8")


def date_stamp() -> str:
    """Local ``YYYY-MM-DD`` stamp for dated backup filenames (respects TIMEZONE)."""
    from django.utils import timezone

    return timezone.localdate().isoformat()


def prune_dated(directory: Path, pattern: str, keep: int = BACKUP_KEEP) -> None:
    """
    Keep the ``keep`` newest files in ``directory`` whose name matches ``pattern``.

    ISO date stamps sort lexicographically, so a reverse name sort puts the
    newest first; everything past ``keep`` is unlinked. ``pattern`` is anchored
    by the caller and scopes the sweep to one artifact set (e.g. only dated DB
    backups, never the ``before-v*`` ones).
    """
    if not directory.is_dir():
        return
    matcher = re.compile(pattern)
    matches = sorted(
        (p for p in directory.iterdir() if matcher.match(p.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    for stale in matches[keep:]:
        stale.unlink(missing_ok=True)
