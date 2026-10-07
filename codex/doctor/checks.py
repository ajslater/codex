"""
What codex itself needs, as rows of the doctor report.

comicbox's doctor covers what comicbox needs. These rows cover the rest:
the database engine, the config directory, each library root, the
filesystem watcher's kernel limits, and the key that decrypts the stored
tagging credentials. Each is a comicbox ``CheckResult`` so the admin page
and the startup log treat them exactly like comicbox's own.

Paths appear here because this is an admin-only page. Nothing from these
rows is ever sent anywhere; the telemeter has its own, count-only report.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from comicbox.doctor import CheckResult, Status
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import connection
from django.db.models import TextField
from django.db.models.functions import Cast
from django.db.utils import OperationalError
from django.template.defaultfilters import filesizeformat

from codex.librarian.fs.mounted import DOCKER_UNMOUNTED_FN
from codex.models.admin import ComicboxTaggingDefaults
from codex.models.collections import Folder
from codex.models.fields import EncryptedCharField
from codex.models.library import Library
from codex.settings import CONFIG_PATH
from codex.util import is_docker

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

SECTION = "Codex"

#: (check name, check). The name labels the ERROR row the runner reports
#: when the check itself crashes.
type Check = Callable[[], Iterable[CheckResult]]

_row = partial(CheckResult, SECTION)

# Below this much free space the config dir row warns: the database, its
# nightly backups, the logs and the cover cache all grow here.
_LOW_DISK_BYTES = 1 << 30
_PERMISSIONS_FIX = "fix its permissions (Docker: PUID and PGID)"

# The kernel's inotify limits, which the event watcher needs one watch per
# folder against. Only Linux has them; macOS and the BSDs watch by other
# means. Per real user across every process, so other watchers share them.
_INOTIFY_DIR = Path("/proc/sys/fs/inotify")
_HAS_INOTIFY = sys.platform == "linux"
# Warn before the limit is reached: other processes draw on the same count.
_WATCH_HEADROOM = 0.8
_WATCHES_SUGGESTED_MIN = 524_288


def check_database() -> Iterator[CheckResult]:
    """SQLite's version, the FTS5 engine search indexes with, and the journal mode."""
    found = f"sqlite {sqlite3.sqlite_version}"
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode")
        mode_row = cursor.fetchone()
        journal_mode = str(mode_row[0] if mode_row else "").lower()
        try:
            # A temp table proves the engine is there; compile options are
            # not recorded in every build.
            cursor.execute(
                "CREATE VIRTUAL TABLE temp.codex_doctor_fts USING fts5(probe)"
            )
            cursor.execute("DROP TABLE temp.codex_doctor_fts")
        except OperationalError as exc:
            yield _row(
                "database",
                Status.MISSING,
                found=found,
                detail=f"no FTS5: comics cannot be search indexed ({exc})",
                fix="use a Python whose sqlite3 was built with FTS5",
            )
            return
    if journal_mode != "wal":
        yield _row(
            "database",
            Status.WARN,
            found=found,
            detail=f"fts5 · journal mode is {journal_mode}, not wal: readers block writers",
            fix="keep the config dir on a local filesystem, not a network share",
        )
        return
    yield _row("database", Status.OK, found=found, detail=f"fts5 · {journal_mode}")


def check_config_dir() -> Iterator[CheckResult]:
    """Check the config dir is writable with room: the database, backups, logs and covers live here."""
    if not os.access(CONFIG_PATH, os.W_OK):
        yield _row(
            "config dir",
            Status.MISCONFIGURED,
            found=CONFIG_PATH,
            detail="not writable: the database, logs, backups and covers live here",
            fix=_PERMISSIONS_FIX,
        )
        return
    free = shutil.disk_usage(CONFIG_PATH).free
    detail = f"writable · {filesizeformat(free)} free"
    if free < _LOW_DISK_BYTES:
        yield _row(
            "config dir",
            Status.WARN,
            found=CONFIG_PATH,
            detail=detail,
            fix="free some space: backups, logs and the cover cache grow here",
        )
        return
    yield _row("config dir", Status.OK, found=CONFIG_PATH, detail=detail)


def _check_library(root: Path, *, read_only: bool) -> CheckResult:
    """One library root: there, readable, and writable unless it is read only."""
    name = "library"
    if not root.is_dir():
        return _row(
            name,
            Status.MISSING,
            found=root,
            detail="not there: its comics look deleted until it is back",
            fix="mount it, or remove the library on the Libraries tab",
        )
    if (root / DOCKER_UNMOUNTED_FN).exists():
        return _row(
            name,
            Status.MISCONFIGURED,
            found=root,
            detail="is the unmounted docker volume, not your comics",
            fix="bind mount the comics directory at this path",
        )
    if not os.access(root, os.R_OK | os.X_OK):
        return _row(
            name,
            Status.MISCONFIGURED,
            found=root,
            detail="not readable",
            fix=_PERMISSIONS_FIX,
        )
    notes = ["readable"]
    if read_only:
        notes.append("read only")
    elif os.access(root, os.W_OK):
        notes.append("writable")
    else:
        return _row(
            name,
            Status.WARN,
            found=root,
            detail="readable · not writable: tag writes and renames fail",
            fix=f"{_PERMISSIONS_FIX}, or mark it read only on the Libraries tab",
        )
    if not any(root.iterdir()):
        return _row(
            name,
            Status.WARN,
            found=root,
            detail=" · ".join([*notes, "empty: suspect unmounted"]),
            fix="mount it, or add comics",
        )
    return _row(name, Status.OK, found=root, detail=" · ".join(notes))


def check_libraries() -> Iterator[CheckResult]:
    """Every library root, in path order."""
    libraries = list(Library.objects.order_by("path").values_list("path", "read_only"))
    if not libraries:
        yield _row(
            "library",
            Status.OFF,
            detail="no libraries",
            fix="add one on the Libraries tab",
        )
        return
    for path, read_only in libraries:
        yield _check_library(Path(path), read_only=read_only)


def _inotify_limit(name: str) -> int:
    return int((_INOTIFY_DIR / name).read_text())


def _suggested_watches(folders: int) -> int:
    """Suggest a limit with room to grow: the usual recommendation, or the next power of two."""
    return max(_WATCHES_SUGGESTED_MIN, 1 << (2 * folders).bit_length())


def check_watcher() -> Iterator[CheckResult]:
    """Whether the kernel lets the event watcher follow every folder it must."""
    roots = Library.objects.filter(events=True).count()
    if not roots:
        yield _row("watcher", Status.OFF, detail="no library watches for events")
        return
    # One inotify watch per directory. Folder rows are the directories
    # codex knows, so this is a floor; comic-less directories add to it.
    folders = Folder.objects.filter(library__events=True).count() + roots
    found = f"{folders} folders"
    if not _HAS_INOTIFY:
        yield _row(
            "watcher", Status.OK, found=found, detail="no kernel watch limit here"
        )
        return
    try:
        max_watches = _inotify_limit("max_user_watches")
    except (OSError, ValueError) as exc:
        yield _row(
            "watcher",
            Status.WARN,
            found=found,
            detail=f"inotify limit unreadable: {exc}",
            fix="check fs.inotify.max_user_watches by hand",
        )
        return
    detail = f"inotify allows {max_watches}"
    host = "the Docker host" if is_docker() else "this host"
    fix = f"sysctl fs.inotify.max_user_watches={_suggested_watches(folders)} on {host}"
    if folders > max_watches:
        yield _row(
            "watcher",
            Status.MISCONFIGURED,
            found=found,
            detail=f"{detail}: changes in the rest go unseen until the next poll",
            fix=fix,
        )
    elif folders > max_watches * _WATCH_HEADROOM:
        yield _row(
            "watcher",
            Status.WARN,
            found=found,
            detail=f"{detail}: nearly all of them, shared with every other watcher",
            fix=fix,
        )
    else:
        yield _row("watcher", Status.OK, found=found, detail=detail)


def check_credentials() -> Iterator[CheckResult]:
    """
    Whether the stored tagging credentials still decrypt.

    The field decrypts on load and, on failure, hands back the ciphertext
    as if it were the value, so the Tagging tab would show gibberish and a
    run would authenticate with it. A read through ``Cast`` skips the
    field's converter and yields what is really stored.
    """
    fields = [
        field
        for field in ComicboxTaggingDefaults._meta.get_fields()
        if isinstance(field, EncryptedCharField)
    ]
    raw = (
        ComicboxTaggingDefaults.objects.filter(pk=1)
        .annotate(**{f"raw_{f.name}": Cast(f.name, TextField()) for f in fields})
        .values(*(f"raw_{f.name}" for f in fields))
        .first()
    ) or {}
    stored: dict[str, str] = {
        f.name: token for f in fields if (token := raw.get(f"raw_{f.name}"))
    }
    if not stored:
        yield _row("credentials", Status.OFF, detail="no tagging credentials stored")
        return
    fernet = Fernet(settings.FIELD_ENCRYPTION_KEY)
    unreadable = []
    for name, token in stored.items():
        try:
            fernet.decrypt(token.encode())
        except InvalidToken:
            unreadable.append(name)
    found = ", ".join(stored)
    if unreadable:
        yield _row(
            "credentials",
            Status.MISCONFIGURED,
            found=", ".join(unreadable),
            detail="cannot be decrypted: the key file in the config dir is not the one they were saved with",
            fix="enter them again on the Tagging tab",
        )
        return
    yield _row("credentials", Status.OK, found=found, detail="decrypt")


CHECKS: tuple[tuple[str, Check], ...] = (
    ("database", check_database),
    ("config dir", check_config_dir),
    ("library", check_libraries),
    ("watcher", check_watcher),
    ("credentials", check_credentials),
)
