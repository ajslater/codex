"""Multi-column sort experiment: append per-key secondary ORDER BY entries."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add ``order_extra_keys`` JSON list to SettingsBrowser."""

    dependencies = [
        ('codex', '0044_browser_table_view_compound_issue_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='settingsbrowser',
            name='order_extra_keys',
            field=models.JSONField(default=list),
        ),
    ]
