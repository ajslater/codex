"""Rename Favorite.group → Favorite.collection (the field holds a collection)."""

from django.db import migrations


class Migration(migrations.Migration):
    """Pure field rename; the column already stores collection values."""

    dependencies = [("codex", "0046_custom_cover_group_collection")]

    operations = [
        migrations.RenameField(
            model_name="favorite",
            old_name="group",
            new_name="collection",
        ),
        migrations.AlterUniqueTogether(
            name="favorite",
            unique_together={("user", "collection", "target_id")},
        ),
    ]
