"""
Rename FTS age_rating to tagged_age_rating and add metron_age_rating.

Also adds the metron_age_rating JSONField column to SettingsBrowserFilters so
the normalized age rating can be used as a browser filter.

The FTS virtual table is dropped and recreated with the new schema — the
search index will be repopulated on the next librarian sync.
"""

from django.db import migrations, models

_NEW_FTS_SQL = (
    "CREATE VIRTUAL TABLE codex_comicfts USING fts5("
    "comic_id UNINDEXED, created_at UNINDEXED, updated_at UNINDEXED, "
    "publisher, imprint, series, name, collection_title, "
    "tagged_age_rating, metron_age_rating, country, language, "
    "original_format, review, scan_info, summary, tagger, characters, "
    "credits, genres, locations, roles, series_groups, stories, "
    "story_arcs, tags, teams, universes, sources"
    ")"
)


class Migration(migrations.Migration):
    """Rename FTS age_rating + add metron_age_rating. Adds filter column too."""

    dependencies = [
        ("codex", "0039_metron_age_rating"),
    ]

    operations = [
        migrations.AddField(
            model_name="settingsbrowserfilters",
            name="metron_age_rating",
            field=models.JSONField(default=list),
        ),
        # ComicFTS is unmanaged; its Django state tracks only (comic, body,
        # created_at, updated_at). The FTS columns are a SQL-level concern —
        # no state_operations are needed, only a raw DROP + CREATE.
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS codex_comicfts;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=_NEW_FTS_SQL,
            reverse_sql="DROP TABLE IF EXISTS codex_comicfts;",
        ),
    ]
