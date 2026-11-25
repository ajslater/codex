"""
Volumes get their own start year, and missing entries a suggestion (1053).

A codex series is a name and a comicbox series one volume run, so the
start year is the volume's. The data step is ``_0062_volume_start_years``.
A missing reading list entry may hold the comic comicbox refused for it,
the issue in another volume or of another cover year, for review.
"""

import django.db.models.deletion
from django.db import migrations, models

import codex.models.fields
from codex.migrations._0062_volume_start_years import volume_start_years


class Migration(migrations.Migration):
    """Add Volume.start_year and ReadingListEntry.suggested_comic."""

    dependencies = [("codex", "0061_reading_lists_and_versedb_key")]

    operations = [
        migrations.AddField(
            model_name="volume",
            name="start_year",
            field=codex.models.fields.CoercingPositiveSmallIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="timestamp",
            name="key",
            field=models.CharField(
                choices=[
                    ("VR", "Codex Version"),
                    ("JA", "Janitor"),
                    ("TS", "Telemeter Sent"),
                    ("FI", "Failed Imports Seen"),
                    ("VY", "Volume Start Years"),
                ],
                db_index=True,
                max_length=2,
            ),
        ),
        migrations.AddField(
            model_name="readinglistentry",
            name="suggested_comic",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="codex.comic",
            ),
        ),
        migrations.RunPython(volume_start_years, migrations.RunPython.noop),
    ]
