"""
Volumes get their own start year (issue 1053).

A codex series is a name and a comicbox series one volume run, so the
start year is the volume's. The data step is ``_0062_volume_start_years``.
"""

from django.db import migrations, models

import codex.models.fields
from codex.migrations._0062_volume_start_years import volume_start_years


class Migration(migrations.Migration):
    """Add Volume.start_year and move what the series held to it."""

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
        migrations.RunPython(volume_start_years, migrations.RunPython.noop),
    ]
