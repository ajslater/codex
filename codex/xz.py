"""
xz (LZMA) helpers for backup artifacts.

Stdlib-only. Backups are streamed into ``lzma`` so memory stays bounded:

* A small DB hands :func:`write_xz_bytes` a consistent binary image from
  ``sqlite3.Connection.serialize()`` (held in RAM).
* A DB too large to hold in RAM is VACUUMed to a temp file and fed through
  :func:`compress_path_to_xz` in fixed-size chunks.
* The user-data sidecar streams ``Connection.iterdump()`` SQL text directly
  into an ``lzma`` text stream (see :mod:`codex.user_data.dump`).

The xz *preset* is chosen from the host's memory budget
(:func:`xz_preset`) so the encoder dictionary — ~94 MiB at preset 6, ~674 MiB
at preset 9 — can't blow a small / cgroup-capped host. Dated nightly backups
accumulate under ``BACKUP_DB_DIR``; :func:`prune_dated` caps each set to
:data:`BACKUP_KEEP`.
"""

from __future__ import annotations

import lzma
import re
import shutil
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

XZ_SUFFIX: Final[str] = ".xz"
# Most recent dated backups to retain per artifact set.
BACKUP_KEEP: Final[int] = 7

_MiB: Final[int] = 1024 * 1024
# Approximate xz *encoder* memory per preset (dictionary-dominated), from the
# xz(1) manual's compression-memory table, rounded up for headroom. Ascending,
# so :func:`xz_preset` can take the last entry that fits the budget.
_PRESET_ENCODER_BYTES: Final[tuple[tuple[int, int], ...]] = (
    (0, 4 * _MiB),
    (1, 11 * _MiB),
    (2, 19 * _MiB),
    (3, 34 * _MiB),
    (4, 51 * _MiB),
    (5, 98 * _MiB),
    (6, 98 * _MiB),
    (7, 192 * _MiB),
    (8, 385 * _MiB),
    (9, 700 * _MiB),
)
# Share of the memory budget the xz encoder dictionary may claim.
_XZ_MEM_FRACTION: Final[float] = 0.25
# Floor: even a tiny host still compresses (preset 0 ≈ 4 MiB encoder).
_MIN_PRESET: Final[int] = 0


def xz_preset(mem_budget_bytes: float | None = None) -> int:
    """
    Richest xz preset whose encoder memory fits the host's budget.

    ``mem_budget_bytes`` defaults to the cgroup-aware
    :func:`codex.librarian.memory.read_mem_limit` (no side effects). A 1 GiB
    host lands around preset 6; an 8 GiB+ host gets the full preset 9.
    """
    if mem_budget_bytes is None:
        from codex.librarian.memory import read_mem_limit

        budget_bytes = read_mem_limit("b")
    else:
        budget_bytes = mem_budget_bytes
    budget = budget_bytes * _XZ_MEM_FRACTION
    best = _MIN_PRESET
    for preset, need in _PRESET_ENCODER_BYTES:
        if need <= budget:
            best = preset
    return best


def write_xz_bytes(data: bytes, dest: Path, *, preset: int) -> None:
    """
    xz-compress an in-memory ``data`` image to ``dest`` atomically.

    Writes a sibling ``.tmp`` then ``replace()``s it into place so a crash
    mid-compress can't leave a truncated backup. The compressor streams to
    disk, so only ``data`` (plus the encoder) is held in memory.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with lzma.open(tmp, "wb", preset=preset) as out:
            out.write(data)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)


def compress_path_to_xz(src: Path, dest: Path, *, preset: int) -> None:
    """
    Stream-compress the file at ``src`` into ``dest`` with bounded memory.

    Used for DBs too large to ``serialize()`` into RAM: ``src`` is a VACUUMed
    temp DB read in ``shutil`` chunks, so peak memory is the xz encoder plus a
    small copy buffer regardless of DB size.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with src.open("rb") as fin, lzma.open(tmp, "wb", preset=preset) as fout:
            shutil.copyfileobj(fin, fout)
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
