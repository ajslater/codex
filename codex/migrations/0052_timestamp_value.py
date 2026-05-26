"""
Rename ``Timestamp.version`` → ``Timestamp.value``.

The column was named ``version`` for historical reasons (the API key
sub-use stored a UUID and the codex-version sub-use stored a SemVer),
but the model holds a generic "last-known value for this key" pair
with an auto-updated timestamp. The new name reads honestly for the
remaining keys (codex-version cache, telemeter install UUID).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Rename Timestamp.version to Timestamp.value."""

    dependencies = [
        ("codex", "0051_move_api_key_to_admin_flag"),
    ]

    operations = [
        migrations.RenameField(
            model_name="timestamp",
            old_name="version",
            new_name="value",
        ),
        migrations.AlterField(
            model_name="timestamp",
            name="value",
            field=models.CharField(default="", max_length=32),
        ),
    ]
