"""
Everything the schema gained after v2.5.5, as one migration.

v2.5.5 shipped through 0057, so nothing here has reached a release. The three
migrations that landed on develop since are folded together: an upgrading
install applies one migration instead of a chain of three.

In order:

- **Series get a year range, a publication status and a summary.** Comicbox's
  series carries them (status is its SeriesStatusEnum, from Metron) and the
  importer merges them per series. The years are nullable and the text columns
  default empty, so existing rows stay empty until their comics are
  re-imported.
- **The browser filters gain series start year, end year and status**, so the
  per-user filter settings get a column for each.
- **The search index gains ``series_summary``.** ``ComicFTS`` is unmanaged, so
  makemigrations never sees it: the column list lives in SQL and has to be
  dropped and recreated by hand, as 0049 did for ``alternate_series``. The
  table comes back empty; the librarian's regular ``SearchIndexSyncTask``
  repopulates it.
- **Comics scanned with tag import on are marked import-complete.** Before
  this release only a forced or lazy import stamped
  ``Comic.metadata_imported_at``. A library scan with the import-tags flag on
  read every comic but stamped none, so a comic with no embedded metadata file
  read as un-imported forever: hovering its tag button re-imported it, purged
  and rebuilt its cover and reloaded the browser. 0043 backfilled the rows
  that existed then; this backfills the ones scanned since, with the same
  seed. Only when the import-tags flag is on: a scan with it off read no tags,
  and its NULL rows are what the lazy importer is for. A missing flag row
  counts as on, its default.

Every step reverses except the backfill, whose reverse is a no-op.
"""

from django.db import migrations, models
from django.db.models.functions import Coalesce

import codex.models.fields

# 0049's column list, for the reverse migration.
_OLD_FTS_SQL = (
    "CREATE VIRTUAL TABLE codex_comicfts USING fts5("
    "comic_id UNINDEXED, created_at UNINDEXED, updated_at UNINDEXED, "
    "publisher, imprint, series, name, collection_title, "
    "age_rating_tagged, age_rating_metron, country, language, "
    "original_format, review, scan_info, summary, tagger, "
    "alternate_series, characters, "
    "credits, genres, locations, roles, series_groups, stories, "
    "story_arcs, tags, teams, universes, sources"
    ")"
)
# 0049's column list plus ``series_summary``.
_NEW_FTS_SQL = (
    "CREATE VIRTUAL TABLE codex_comicfts USING fts5("
    "comic_id UNINDEXED, created_at UNINDEXED, updated_at UNINDEXED, "
    "publisher, imprint, series, name, collection_title, "
    "age_rating_tagged, age_rating_metron, country, language, "
    "original_format, review, scan_info, summary, series_summary, tagger, "
    "alternate_series, characters, "
    "credits, genres, locations, roles, series_groups, stories, "
    "story_arcs, tags, teams, universes, sources"
    ")"
)
_DROP_FTS_SQL = "DROP TABLE IF EXISTS codex_comicfts;"

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
    """Series fields and filters, FTS series_summary, imported-at backfill."""

    dependencies = [
        ("codex", "0057_remove_pinned_settings"),
    ]

    operations = [
        # Series year range, status and summary.
        migrations.AddField(
            model_name="series",
            name="end_year",
            field=codex.models.fields.CoercingPositiveSmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="series",
            name="start_year",
            field=codex.models.fields.CoercingPositiveSmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="series",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Ongoing", "Ongoing"),
                    ("Cancelled", "Cancelled"),
                    ("Completed", "Completed"),
                    ("Hiatus", "Hiatus"),
                ],
                default="",
                max_length=9,
            ),
        ),
        migrations.AddField(
            model_name="series",
            name="summary",
            field=codex.models.fields.CleaningTextField(
                blank=True, db_collation="nocase", default=""
            ),
        ),
        # Series filter columns, then the FTS series_summary column.
        migrations.AddField(
            model_name="settingsbrowserfilters",
            name="series_end_year",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="settingsbrowserfilters",
            name="series_start_year",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="settingsbrowserfilters",
            name="series_status",
            field=models.JSONField(default=list),
        ),
        # ComicFTS is unmanaged; its Django state tracks only (comic,
        # created_at, updated_at). The FTS columns are a SQL-level concern —
        # no state_operations are needed, only a raw DROP + CREATE. Unlike
        # 0049, the reverse restores the previous table rather than none.
        migrations.RunSQL(sql=_DROP_FTS_SQL, reverse_sql=_OLD_FTS_SQL),
        migrations.RunSQL(sql=_NEW_FTS_SQL, reverse_sql=_DROP_FTS_SQL),
        # The metadata_imported_at backfill.
        migrations.RunPython(_backfill_metadata_imported_at, migrations.RunPython.noop),
    ]
