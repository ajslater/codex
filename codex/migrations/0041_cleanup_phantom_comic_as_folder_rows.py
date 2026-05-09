"""
Delete corrupt Comic rows whose ``path`` points at a directory.

Background
==========

Through v1.11.4 the snapshot diff matched moves by ``(device, inode)``
with ``device`` forced to 0 to ride out Docker bind-mount remounts.
That fix protected against false-modify storms on remount but left a
much rarer collision unguarded: a comic file's stored inode could
randomly equal an unrelated *directory's* current disk inode on a
different device. The diff treated that as a rename, the importer
rewrote the Comic row's ``path`` to the directory, and
``Comic.presave()`` re-read disk stat — picking up the directory's
mode bits and size — leaving a "phantom Comic-as-folder" row in the
database. The original comic file then re-imported as a fresh row
on the next cycle, orphaning bookmarks.

The companion code change (``SnapshotDiff._is_move_compatible``)
prevents new rows from being corrupted; this migration cleans up
rows already corrupted by past runs.

Detection
=========

A corrupt row has all of:

- A non-comic-suffix ``path`` (the original importer bug's
  page_count==0 phantoms had this too — migration 0039 cleaned
  those up but only when ``page_count == 0``; corruption from the
  inode-collision path inherits the original comic's page_count
  and slipped through).
- A ``stat[0]`` mode field with the directory bit set, OR a
  ``Path(path)`` that resolves to a directory on disk now.

We require *both* a non-comic suffix and a directory signal so a
genuinely-named comic with a transient stat read isn't deleted by
mistake.

Safety
======

If the comics volume is unmounted at migration time, every
``Path.is_dir()`` returns False and we'd do nothing — fine. But
``stat[0]``-based detection still fires from the stored data, so
add the same FS-reachable sentinel migration 0039 uses: only
proceed if at least one comic-suffix path stats as a real file.
"""

import re
from pathlib import Path
from stat import S_ISDIR

from django.db import migrations
from loguru import logger

_COMIC_SUFFIX_RE = re.compile(r"^\.(cbz|cbr|cbt|cb7|pdf)$", re.IGNORECASE)
_SENTINEL_LIMIT = 32
_STAT_LEN = 10
_STAT_MODE_INDEX = 0


def _is_comic_path(path_str: str) -> bool:
    if not path_str:
        return False
    suffix = Path(path_str).suffix
    return bool(suffix) and _COMIC_SUFFIX_RE.match(suffix) is not None


def _comics_fs_reachable(model) -> tuple[bool, int]:
    """
    Probe up to ``_SENTINEL_LIMIT`` comic-suffix paths to verify the FS is mounted.

    Mirrors migration 0039's approach. Returns ``(reachable, attempts)``.
    Reachable as soon as one comic-suffix path stats as a file. If no
    successes, the FS is unreachable and the caller skips the cleanup.
    """
    attempts = 0
    for comic in model.objects.only("path").iterator():
        path_str = comic.path or ""
        if not _is_comic_path(path_str):
            continue
        attempts += 1
        try:
            if Path(path_str).is_file():
                return True, attempts
        except OSError:
            pass
        if attempts >= _SENTINEL_LIMIT:
            break
    return False, attempts


def _stat_says_directory(stat_value) -> bool:
    """Whether the stored stat array's mode bits mark this row as a directory."""
    if not stat_value or len(stat_value) != _STAT_LEN:
        return False
    mode = stat_value[_STAT_MODE_INDEX]
    if not isinstance(mode, int):
        return False
    return S_ISDIR(mode)


def _path_says_directory(path_str: str) -> bool:
    """Whether the path resolves to a directory on disk right now."""
    try:
        return Path(path_str).is_dir()
    except OSError:
        return False


def _find_corrupt_comic_pks(model) -> tuple[int, ...]:
    """Find Comic rows whose path points at a directory (or non-comic non-file)."""
    delete_pks: list[int] = []
    qs = model.objects.only("pk", "path", "stat")
    for comic in qs.iterator():
        path_str = comic.path or ""
        if _is_comic_path(path_str):
            # Genuinely a comic archive name; leave it alone even if
            # the stored stat is bogus — that's a different repair.
            continue
        if _stat_says_directory(comic.stat) or _path_says_directory(path_str):
            delete_pks.append(comic.pk)
    return tuple(delete_pks)


def _cleanup_phantom_comic_as_folder_rows(apps, _schema_editor) -> None:
    """Delete Comic rows whose path is a directory."""
    model = apps.get_model("codex", "Comic")

    reachable, sentinel_attempts = _comics_fs_reachable(model)
    if not reachable:
        if sentinel_attempts == 0:
            msg = (
                "Skipping phantom Comic-as-folder cleanup: no comic-suffix "
                "paths in the database to use as a stat sentinel."
            )
            logger.info(msg)
        else:
            msg = (
                f"Skipping phantom Comic-as-folder cleanup: probed "
                f"{sentinel_attempts} comic-suffix paths and none stat as "
                "files. If your comics volume is not mounted, restart with "
                "it attached so this cleanup can run."
            )
            logger.warning(msg)
        return

    delete_pks = _find_corrupt_comic_pks(model)
    if not delete_pks:
        return
    msg = (
        f"Deleting {len(delete_pks)} phantom Comic-as-folder rows from "
        "codex_comic. Affected bookmarks will be lost — see PR notes."
    )
    logger.info(msg)
    model.objects.filter(pk__in=delete_pks).delete()


def _noop(_apps, _schema_editor) -> None:
    """Reverse no-op (data migrations stay applied on rollback)."""


class Migration(migrations.Migration):
    """One-time cleanup of Comic rows whose path points at a directory."""

    dependencies = [
        ("codex", "0040_reset_global_cache_book"),
    ]

    operations = [
        migrations.RunPython(_cleanup_phantom_comic_as_folder_rows, _noop),
    ]
