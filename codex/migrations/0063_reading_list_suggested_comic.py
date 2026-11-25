"""
A missing reading list entry may hold a suggested comic (issue 1053).

comicbox reports the comics it refused for an entry it left missing: the
issue in another volume, or of another cover year. Review shows the
likeliest so a person may pick it.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add ReadingListEntry.suggested_comic."""

    dependencies = [("codex", "0062_volume_start_year")]

    operations = [
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
    ]
