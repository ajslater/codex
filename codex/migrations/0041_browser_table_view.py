"""
Browser table view + cleanup of phantom Comic-as-folder rows.

Consolidates work that originally landed across separate migrations on
two branches:

Browser table view (``browser-table-view`` branch, was 0041-0045)
=================================================================

- Add ``view_mode``, ``table_columns``, and ``table_cover_size`` to
  ``SettingsBrowser``. ``table_cover_size`` ships with only the
  ``sm`` choice — the original ``xs`` option was dropped before the
  feature shipped.
- Re-state ``order_by`` choices to the post-table-view list:
  the 13-key starter set from migration 0038 plus ~30 additions
  (per-relation FK names, M2M-sort keys, plus a single ``issue``
  key that supersedes the original ``issue_number`` /
  ``issue_suffix`` pair).
- Add ``order_extra_keys`` JSON list for multi-column-sort tiebreakers.

These are pure choice-metadata edits on existing ``CharField``
columns plus three ``AddField``s; Django emits ``ALTER TABLE`` only
for the new columns.

Phantom Comic-as-folder cleanup (``develop`` branch, was 0041)
==============================================================

Through v1.11.4 the snapshot diff matched moves by ``(device,
inode)`` with ``device`` forced to 0 to ride out Docker bind-mount
remounts. That fix protected against false-modify storms on remount
but left a much rarer collision unguarded: a comic file's stored
inode could randomly equal an unrelated *directory's* current disk
inode on a different device. The diff treated that as a rename, the
importer rewrote the Comic row's ``path`` to the directory, and
``Comic.presave()`` re-read disk stat — picking up the directory's
mode bits and size — leaving a "phantom Comic-as-folder" row in the
database. The original comic file then re-imported as a fresh row
on the next cycle, orphaning bookmarks.

The companion code change (``SnapshotDiff._is_move_compatible``)
prevents new rows from being corrupted; this migration cleans up
rows already corrupted by past runs. Migration 0039's
``_remove_non_comic_comics`` only targeted ``page_count == 0`` rows
(the original importer-bug signature); rows corrupted by the
inode-collision path inherit their original ``page_count`` and
slipped through that filter.

Detection requires *both* a non-comic-suffix ``path`` and a
directory signal (``stat[0]`` mode bits or ``Path(path).is_dir()``)
so a genuinely-named comic with a transient stat read isn't deleted
by mistake. Reuses the FS-reachable sentinel from 0039 — if the
comics volume is unmounted, skip the cleanup rather than risk
deleting against a phantom-empty disk.
"""

import re
from pathlib import Path
from stat import S_ISDIR

from django.db import migrations, models
from loguru import logger

# ----------------------------------------------------------------------
# Phantom Comic-as-folder cleanup helpers (from develop's 0041).
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Final post-table-view ``order_by`` choice list (from 0044's state).
# Drops the original ``issue_number`` / ``issue_suffix`` pair in favor
# of a single compound ``issue`` entry; includes the M2M-sort keys
# from 0043.
# ----------------------------------------------------------------------

_ORDER_BY_CHOICES = [
    ("created_at", "Added Time"),
    ("age_rating", "Age Rating"),
    ("characters", "Characters"),
    ("child_count", "Child Count"),
    ("country", "Country"),
    ("credits", "Credits"),
    ("critical_rating", "Critical Rating"),
    ("day", "Day"),
    ("filename", "Filename"),
    ("size", "File Size"),
    ("file_type", "File Type"),
    ("original_format", "Format"),
    ("genres", "Genres"),
    ("identifiers", "Identifiers"),
    ("imprint_name", "Imprint"),
    ("issue", "Issue"),
    ("language", "Language"),
    ("bookmark_updated_at", "Last Read"),
    ("locations", "Locations"),
    ("main_character", "Main Character"),
    ("main_team", "Main Team"),
    ("metadata_mtime", "Metadata Updated"),
    ("month", "Month"),
    ("monochrome", "Monochrome"),
    ("sort_name", "Name"),
    ("page_count", "Page Count"),
    ("publisher_name", "Publisher"),
    ("date", "Publish Date"),
    ("reading_direction", "Reading Direction"),
    ("scan_info", "Scan Info"),
    ("search_score", "Search Score"),
    ("series_name", "Series"),
    ("series_groups", "Series Groups"),
    ("stories", "Stories"),
    ("story_arc_number", "Story Arc Number"),
    ("story_arcs", "Story Arcs"),
    ("tags", "Tags"),
    ("tagger", "Tagger"),
    ("teams", "Teams"),
    ("universes", "Universes"),
    ("updated_at", "Updated Time"),
    ("volume_name", "Volume"),
    ("year", "Year"),
]


class Migration(migrations.Migration):
    """Add table-view fields to ``SettingsBrowser`` and clean phantom Comic rows."""

    dependencies = [
        ("codex", "0040_reset_global_cache_book"),
    ]

    operations = [
        # New table-view fields.
        migrations.AddField(
            model_name="settingsbrowser",
            name="table_columns",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="settingsbrowser",
            name="table_cover_size",
            field=models.CharField(
                choices=[("sm", "Small")],
                default="sm",
                max_length=4,
            ),
        ),
        migrations.AddField(
            model_name="settingsbrowser",
            name="view_mode",
            field=models.CharField(
                choices=[("cover", "Cover"), ("table", "Table")],
                default="cover",
                max_length=8,
            ),
        ),
        # Multi-column-sort tiebreakers.
        migrations.AddField(
            model_name="settingsbrowser",
            name="order_extra_keys",
            field=models.JSONField(default=list),
        ),
        # Refresh ``order_by`` choices to the final post-table-view set.
        migrations.AlterField(
            model_name="settingsbrowser",
            name="order_by",
            field=models.CharField(
                choices=_ORDER_BY_CHOICES,
                default="",
                max_length=32,
            ),
        ),
        # One-time data cleanup for inode-collision corruption.
        migrations.RunPython(_cleanup_phantom_comic_as_folder_rows, _noop),
    ]
