"""Rename SettingsBrowserLastRoute.group → .collection (holds a collection)."""

from django.db import migrations


class Migration(migrations.Migration):
    """Pure field rename; the column already stores collection values."""

    dependencies = [("codex", "0048_rename_custom_cover_group_to_collection")]

    operations = [
        migrations.RenameField(
            model_name="settingsbrowserlastroute",
            old_name="group",
            new_name="collection",
        ),
    ]
