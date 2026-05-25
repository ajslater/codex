"""Add REGISTER_VERIFICATION admin flag choice."""

from django.db import migrations, models

# Mirrors codex.choices.admin.AdminFlagChoices in alphabetical-by-code
# order at the time this migration was authored. Future additions append
# to the same list.
_ADMIN_FLAG_KEY_CHOICES = [
    ("AA", "Anonymous User Age Rating"),
    ("AR", "Age Rating Default"),
    ("AU", "Auto Update"),
    ("BT", "Banner Text"),
    ("BG", "Browser Default Group"),
    ("FV", "Folder View"),
    ("IM", "Import Metadata"),
    ("LI", "Lazy Import Metadata"),
    ("NU", "Non Users"),
    ("RG", "Registration"),
    ("RV", "Register Verification"),
    ("ST", "Send Telemetry"),
]


class Migration(migrations.Migration):
    """Extend AdminFlag.key choices with REGISTER_VERIFICATION."""

    dependencies = [
        ("codex", "0043_comicbox_tagging_defaults"),
    ]

    operations = [
        migrations.AlterField(
            model_name="adminflag",
            name="key",
            field=models.CharField(
                choices=_ADMIN_FLAG_KEY_CHOICES, db_index=True, max_length=2
            ),
        ),
    ]
