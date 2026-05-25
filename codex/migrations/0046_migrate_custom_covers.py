"""
Custom cover data migration — step 2.

Moves every legacy custom-cover file into the new pk-keyed uploads
directory, detaches rows from the synthetic covers-only ``Library``,
deletes that Library row, and best-effort scrubs leftover files from
the old layout. Idempotent: rows already living under
``uploads/`` are skipped.
"""

import contextlib
import shutil
from pathlib import Path

from django.db import migrations
from loguru import logger

from codex.settings import (
    CUSTOM_COVERS_DIR,
    CUSTOM_COVERS_GROUP_DIRS,
    CUSTOM_COVERS_UPLOADS_DIR,
)

# Inline copies of the maps the live code uses, frozen at this
# migration's point in time. Live constants can drift; data
# migrations must replay deterministically against old DBs.
_GROUP_CHAR_TO_MODEL_NAME = {
    "p": "publisher",
    "i": "imprint",
    "s": "series",
    "v": "volume",
    "a": "storyarc",
    "f": "folder",
}


def _slugify(name: str) -> str:
    """Filesystem-safe slug derived from a group's sort_name."""
    if not name:
        return ""
    keep = []
    for ch in name.lower():
        if ch.isalnum():
            keep.append(ch)
        elif keep and keep[-1] != "-":
            keep.append("-")
    slug = "".join(keep).strip("-")
    return slug[:60]


def _resolve_slug(cover, apps) -> str:
    """Pick a human slug from the linked group, if any."""
    model_name = _GROUP_CHAR_TO_MODEL_NAME.get(cover.group)
    if not model_name:
        return ""
    model = apps.get_model("codex", model_name)
    linked = model.objects.filter(custom_cover_id=cover.pk).first()
    if linked is None:
        return ""
    raw = getattr(linked, "sort_name", "") or getattr(linked, "name", "") or ""
    return _slugify(str(raw))


def _new_path(cover, slug: str) -> Path:
    """Build the new uploads/-rooted path for a cover row."""
    ext = Path(cover.path).suffix.lower() or ".jpg"
    stem = f"{cover.pk}-{cover.group}"
    if slug:
        stem = f"{stem}-{slug}"
    return CUSTOM_COVERS_UPLOADS_DIR / f"{stem}{ext}"


def _move_to_uploads(apps) -> None:
    custom_cover_model = apps.get_model("codex", "customcover")
    CUSTOM_COVERS_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for cover in custom_cover_model.objects.all():
        src = Path(cover.path)
        try:
            src.relative_to(CUSTOM_COVERS_UPLOADS_DIR)
        except ValueError:
            pass
        else:
            # Already under uploads/: just detach and continue.
            if cover.library_id is not None:
                cover.library = None
                cover.save(update_fields=["library"])
            continue

        if not src.is_file():
            logger.warning(f"Custom cover source file missing, skipping: {src}")
            cover.library = None
            cover.save(update_fields=["library"])
            continue

        slug = _resolve_slug(cover, apps)
        dest = _new_path(cover, slug)
        try:
            shutil.move(str(src), str(dest))
        except OSError as exc:
            logger.warning(f"Failed to move custom cover {src} -> {dest}: {exc}")
            continue
        cover.path = str(dest)
        cover.library = None
        cover.save(update_fields=["path", "library"])


def _scrub_legacy() -> None:
    """Best-effort: remove any leftover files under the legacy group dirs."""
    for group_dir in CUSTOM_COVERS_GROUP_DIRS:
        legacy = CUSTOM_COVERS_DIR / group_dir
        if not legacy.is_dir():
            continue
        for path in legacy.iterdir():
            if path.is_file():
                try:
                    path.unlink()
                except OSError as exc:
                    logger.warning(
                        f"Could not unlink legacy custom cover {path}: {exc}"
                    )
        with contextlib.suppress(OSError):
            legacy.rmdir()


def _delete_covers_only_library(apps) -> None:
    library_model = apps.get_model("codex", "library")
    library_model.objects.filter(covers_only=True).delete()


def forwards(apps, _schema_editor) -> None:
    """Run the migration."""
    _move_to_uploads(apps)
    _scrub_legacy()
    _delete_covers_only_library(apps)


class Migration(migrations.Migration):
    """Custom cover schema step 2: move legacy files, delete covers-only library."""

    dependencies = [
        ("codex", "0045_custom_covers_step1"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
