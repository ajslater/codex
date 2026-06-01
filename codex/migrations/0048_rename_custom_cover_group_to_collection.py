"""Rename CustomCover.group → CustomCover.collection (holds a collection)."""

from django.db import migrations


class Migration(migrations.Migration):
    """Pure field rename; the column already stores collection values."""

    dependencies = [("codex", "0047_rename_favorite_group_to_collection")]

    operations = [
        migrations.RenameField(
            model_name="customcover",
            old_name="group",
            new_name="collection",
        ),
    ]
