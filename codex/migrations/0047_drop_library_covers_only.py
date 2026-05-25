"""
Custom cover schema — step 3.

Drops ``Library.covers_only`` now that the data migration has detached
every upload from the synthetic covers-only library and deleted that
row. ``CustomCover.library`` stays nullable; it's always NULL going
forward but pruning the column is a separate, more invasive change.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Custom cover schema step 3: drop ``Library.covers_only``."""

    dependencies = [
        ("codex", "0046_migrate_custom_covers"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="library",
            name="covers_only",
        ),
    ]
