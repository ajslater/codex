"""
Mark comics scanned with tag import on as import-complete.

Before this release, only a forced or lazy import stamped
``Comic.metadata_imported_at``. A library scan with the import-tags flag on
read every comic but stamped none, so a comic with no embedded metadata file
read as un-imported forever. Hovering its tag button re-imported it, purged
and rebuilt its cover and reloaded the browser. 0043 backfilled the rows that
existed then; this backfills the ones scanned since, with the same seed.

Only when the import-tags flag is on: a scan with it off read no tags, and
its NULL rows are what the lazy importer is for. A missing flag row counts
as on, its default.
"""

from django.db import migrations
from django.db.models.functions import Coalesce

# AdminFlagChoices.IMPORT_METADATA, frozen at this migration's point in time.
_IMPORT_METADATA_KEY = "IM"


def _backfill_metadata_imported_at(apps, _schema_editor) -> None:
    """Stamp un-stamped comics if library scans import tags."""
    admin_flag_model = apps.get_model("codex", "adminflag")
    flag = admin_flag_model.objects.filter(key=_IMPORT_METADATA_KEY).first()
    if flag is not None and not flag.on:
        return
    comic_model = apps.get_model("codex", "comic")
    comic_model.objects.filter(metadata_imported_at__isnull=True).update(
        metadata_imported_at=Coalesce("metadata_mtime", "updated_at")
    )


class Migration(migrations.Migration):
    """Backfill Comic.metadata_imported_at for comics scanned since 0043."""

    dependencies = [
        ("codex", "0059_series_filters_and_fts_summary"),
    ]

    operations = [
        migrations.RunPython(_backfill_metadata_imported_at, migrations.RunPython.noop),
    ]
