"""Rename SettingsBrowser.top_group → top_collection (holds a collection)."""

from django.db import migrations


class Migration(migrations.Migration):
    """Pure field rename; the column already stores collection values."""

    dependencies = [("codex", "0049_rename_last_route_group_to_collection")]

    operations = [
        migrations.RenameField(
            model_name="settingsbrowser",
            old_name="top_group",
            new_name="top_collection",
        ),
    ]
