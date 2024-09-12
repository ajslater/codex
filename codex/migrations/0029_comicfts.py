"""Generated by Django 5.0.8 on 2024-08-07 22:07."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Run migrations."""

    dependencies = [
        ("codex", "0028_telemeter"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="ComicFTS",
                    fields=[
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "comic",
                            models.OneToOneField(
                                on_delete=django.db.models.deletion.CASCADE,
                                primary_key=True,
                                serialize=False,
                                to="codex.comic",
                            ),
                        ),
                        ("body", models.TextField()),
                    ],
                    options={
                        "get_latest_by": "updated_at",
                        "managed": False,
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE VIRTUAL TABLE codex_comicfts USING fts5("
                        "comic_id UNINDEXED, created_at UNINDEXED, "
                        "updated_at UNINDEXED, "
                        "publisher, imprint, series, volume, issue, name, age_rating, "
                        "country, language, "
                        "notes, original_format, review, scan_info, summary, "
                        "tagger, "
                        "characters, contributors, genres,"
                        "locations, roles, series_groups, stories, "
                        "story_arcs, tags, teams, "
                        "reading_direction, file_type)"
                    ),
                    reverse_sql="DROP TABLE IF EXISTS codex_comicfts",
                ),
            ],
        )
    ]
