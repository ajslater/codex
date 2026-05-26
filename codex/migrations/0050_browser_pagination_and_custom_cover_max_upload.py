"""
Add MP and CM admin-flag choices; seed BROWSER_MAX_OBJ_PER_PAGE from TOML/env.

``MP`` (Browser Max Objects Per Page) is migrated from
``settings.BROWSER_MAX_OBJ_PER_PAGE`` so admins do not lose their
TOML-configured page size when the runtime UI takes over. ``CM``
(Custom Cover Max Upload MB) is a new admin-controlled cap and seeds
with the model default (10 MB) — the TOML value is left in place as the
fallback for fresh installs before first admin save.
"""

import django.db.migrations.operations.special
from django.conf import settings
from django.db import migrations, models

# Mirrors codex.choices.admin.AdminFlagChoices at the time this
# migration was authored.
_ADMIN_FLAG_KEY_CHOICES = [
    ("AA", "Anonymous User Age Rating"),
    ("AR", "Age Rating Default"),
    ("AU", "Auto Update"),
    ("BT", "Banner Text"),
    ("BG", "Browser Default Group"),
    ("CM", "Custom Cover Max Upload Mb"),
    ("FV", "Folder View"),
    ("IM", "Import Metadata"),
    ("LI", "Lazy Import Metadata"),
    ("MP", "Browser Max Obj Per Page"),
    ("NU", "Non Users"),
    ("RG", "Registration"),
    ("RV", "Register Verification"),
    ("ST", "Send Telemetry"),
]


def seed_value_flags(apps, _schema_editor):
    """Seed MP from settings and CM with the default upload cap."""
    AdminFlag = apps.get_model("codex", "AdminFlag")
    mp_value = str(getattr(settings, "BROWSER_MAX_OBJ_PER_PAGE", 100) or 100)
    cm_value = str(getattr(settings, "CUSTOM_COVERS_MAX_UPLOAD_MB", 10) or 10)
    AdminFlag.objects.update_or_create(
        key="MP",
        defaults={"on": True, "value": mp_value},
    )
    AdminFlag.objects.update_or_create(
        key="CM",
        defaults={"on": True, "value": cm_value},
    )


class Migration(migrations.Migration):
    """Extend AdminFlag.key choices and seed MP / CM rows."""

    dependencies = [
        ("codex", "0049_throttle_settings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="adminflag",
            name="key",
            field=models.CharField(
                choices=_ADMIN_FLAG_KEY_CHOICES, db_index=True, max_length=2
            ),
        ),
        migrations.RunPython(
            code=seed_value_flags,
            reverse_code=django.db.migrations.operations.special.RunPython.noop,
        ),
    ]
