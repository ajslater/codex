"""
Series filters and a searchable series summary.

The browser filters gain the series start year, end year and status, so
the per-user filter settings get a column for each.

The FTS5 rebuild adds the ``series_summary`` column. ``ComicFTS`` is
unmanaged, so makemigrations never sees it — the column list lives in
SQL and has to be dropped and recreated by hand, as 0049 did for
``alternate_series``. The table comes back empty; the librarian's
regular ``SearchIndexSyncTask`` repopulates it.
"""

from django.db import migrations, models

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


class Migration(migrations.Migration):
    """Series filter columns and FTS series_summary."""

    dependencies = [
        ("codex", "0058_series_fields"),
    ]

    operations = [
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
    ]
