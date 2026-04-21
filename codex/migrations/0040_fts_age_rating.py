"""
Rebuild the ComicFTS virtual table with the new age-rating columns.

Adds ``age_rating_tagged`` (original tagged name) and ``age_rating_metron``
(normalized Metron value) as first-class FTS columns — replacing the single
``age_rating`` column from 0029. ``ComicFTS`` is unmanaged; its Django state
only tracks ``comic`` + timestamps, so the full column list is owned by
SQL. The search index will be repopulated on the next librarian sync.
"""

from django.db import migrations

_NEW_FTS_SQL = (
    "CREATE VIRTUAL TABLE codex_comicfts USING fts5("
    "comic_id UNINDEXED, created_at UNINDEXED, updated_at UNINDEXED, "
    "publisher, imprint, series, name, collection_title, "
    "age_rating_tagged, age_rating_metron, country, language, "
    "original_format, review, scan_info, summary, tagger, characters, "
    "credits, genres, locations, roles, series_groups, stories, "
    "story_arcs, tags, teams, universes, sources"
    ")"
)


class Migration(migrations.Migration):
    """Rebuild ComicFTS with ``age_rating_tagged`` + ``age_rating_metron``."""

    dependencies = [
        ("codex", "0039_metron_age_rating"),
    ]

    operations = [
        # ComicFTS is unmanaged; its Django state tracks only (comic,
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
