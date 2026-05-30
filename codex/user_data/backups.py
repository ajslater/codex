"""
Naming, listing, and safe resolution of user-data sidecar backups.

Sidecar snapshots are dated, xz-compressed SQL dumps that live alongside the
DB backups in ``BACKUP_DB_DIR`` (e.g. ``user_data.2026-05-29.sql.xz``). This
module is the single source of truth for that filename shape so the writer
(:mod:`codex.user_data.dump`), the restore path, and the admin "pick a backup"
UI all agree.

A legacy uncompressed binary ``user_data.sqlite`` (the pre-compression sidecar)
in ``CONFIG_PATH`` is also surfaced so an upgraded install can still restore
from it until the first nightly snapshot replaces it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, TypedDict

from codex.xz import date_stamp

if TYPE_CHECKING:
    from pathlib import Path

# ``user_data.<ISO-date>.sql.xz`` — the dated sidecar snapshot.
SIDECAR_BACKUP_PATTERN: Final[str] = r"^user_data\.\d{4}-\d{2}-\d{2}\.sql\.xz$"
_SIDECAR_BACKUP_RE: Final = re.compile(SIDECAR_BACKUP_PATTERN)
_LEGACY_BINARY_NAME: Final[str] = "user_data.sqlite"


class SidecarBackup(TypedDict):
    """One selectable sidecar backup for the admin restore UI."""

    name: str
    label: str
    size: int
    mtime: float


def sidecar_backup_path(backup_dir: Path) -> Path:
    """Today's dated sidecar snapshot path inside ``backup_dir``."""
    return backup_dir / f"user_data.{date_stamp()}.sql.xz"


def list_sidecar_backups(backup_dir: Path, config_dir: Path) -> list[SidecarBackup]:
    """
    Every restorable sidecar, newest first.

    Dated ``.sql.xz`` snapshots in ``backup_dir`` plus, last, a legacy binary
    ``user_data.sqlite`` in ``config_dir`` if one is still present.
    """
    backups: list[SidecarBackup] = []
    if backup_dir.is_dir():
        dated = [p for p in backup_dir.iterdir() if _SIDECAR_BACKUP_RE.match(p.name)]
        # Name sort == date sort (ISO); newest first.
        for path in sorted(dated, key=lambda p: p.name, reverse=True):
            stat = path.stat()
            # Strip the ``user_data.`` prefix and ``.sql.xz`` suffix → the date.
            label = path.name[len("user_data.") : -len(".sql.xz")]
            backups.append(
                {
                    "name": path.name,
                    "label": label,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
            )
    legacy = config_dir / _LEGACY_BINARY_NAME
    if legacy.is_file():
        stat = legacy.stat()
        backups.append(
            {
                "name": _LEGACY_BINARY_NAME,
                "label": "legacy (uncompressed)",
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
        )
    return backups


def resolve_sidecar_backup(
    name: str, backup_dir: Path, config_dir: Path
) -> Path | None:
    """
    Map a client-supplied backup ``name`` to a path, or ``None`` if invalid.

    Only the basename is honored (no directory traversal): a dated snapshot
    must match the strict pattern and exist in ``backup_dir``; the single
    legacy binary name resolves into ``config_dir``.
    """
    from pathlib import Path as _Path

    base = _Path(name).name
    if _SIDECAR_BACKUP_RE.match(base):
        candidate = backup_dir / base
        return candidate if candidate.is_file() else None
    if base == _LEGACY_BINARY_NAME:
        candidate = config_dir / base
        return candidate if candidate.is_file() else None
    return None


def newest_sidecar_backup(backup_dir: Path, config_dir: Path) -> Path | None:
    """Return the most recent sidecar backup path, or ``None`` if there are none."""
    backups = list_sidecar_backups(backup_dir, config_dir)
    if not backups:
        return None
    return resolve_sidecar_backup(backups[0]["name"], backup_dir, config_dir)
