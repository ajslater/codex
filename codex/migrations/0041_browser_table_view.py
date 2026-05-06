"""Add browser table-view settings fields to ``SettingsBrowser``."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add ``view_mode``, ``table_columns``, and ``table_cover_size``."""

    dependencies = [
        ("codex", "0040_reset_global_cache_book"),
    ]

    operations = [
        migrations.AddField(
            model_name="settingsbrowser",
            name="table_columns",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="settingsbrowser",
            name="table_cover_size",
            field=models.CharField(
                choices=[("xs", "Tiny"), ("sm", "Small")],
                default="sm",
                max_length=4,
            ),
        ),
        migrations.AddField(
            model_name="settingsbrowser",
            name="view_mode",
            field=models.CharField(
                choices=[("cover", "Cover"), ("table", "Table")],
                default="cover",
                max_length=8,
            ),
        ),
    ]
