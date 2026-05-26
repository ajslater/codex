"""
Move the API key from Timestamp to AdminFlag.

Timestamp held a row keyed ``AP`` with the UUID API key in its
``version`` column. The other Timestamp rows are internal operational
state (codex-version cache, janitor run marker, telemeter install UUID
and last-send marker), but the API key was admin-managed configuration
that incidentally lived in the same table.

This migration:

* Copies the existing API key string from the ``Timestamp`` row into a
  new ``AdminFlag`` row keyed ``AK``.
* Deletes the old ``Timestamp`` row.
* Updates the ``choices`` metadata on both fields.

If the Timestamp row is missing (fresh install) the AdminFlag row is
seeded with an empty value; ``init_admin_flags`` at boot fills it with
a freshly-generated UUID via the same code path that handled the
Timestamp.AP row before.
"""

from django.db import migrations, models

_ADMIN_FLAG_KEY_CHOICES = [
    ("AA", "Anonymous User Age Rating"),
    ("AK", "Api Key"),
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

_TIMESTAMP_KEY_CHOICES = [
    ("VR", "Codex Version"),
    ("JA", "Janitor"),
    ("TS", "Telemeter Sent"),
]


def _move_api_key(apps, _schema_editor):
    """Copy Timestamp.AP.version into AdminFlag.AK.value, then delete the row."""
    AdminFlag = apps.get_model("codex", "AdminFlag")
    Timestamp = apps.get_model("codex", "Timestamp")
    existing = Timestamp.objects.filter(key="AP").first()
    api_key_value = existing.version if existing is not None else ""
    AdminFlag.objects.update_or_create(
        key="AK",
        defaults={"on": True, "value": api_key_value},
    )
    if existing is not None:
        existing.delete()


def _restore_api_key(apps, _schema_editor):
    """Reverse: copy AdminFlag.AK back into a Timestamp.AP row."""
    AdminFlag = apps.get_model("codex", "AdminFlag")
    Timestamp = apps.get_model("codex", "Timestamp")
    flag = AdminFlag.objects.filter(key="AK").first()
    api_key_value = flag.value if flag is not None else ""
    Timestamp.objects.update_or_create(
        key="AP",
        defaults={"version": api_key_value},
    )
    if flag is not None:
        flag.delete()


class Migration(migrations.Migration):
    """Migrate API key from Timestamp to AdminFlag."""

    dependencies = [
        ("codex", "0050_browser_pagination_and_custom_cover_max_upload"),
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
            code=_move_api_key,
            reverse_code=_restore_api_key,
        ),
        migrations.AlterField(
            model_name="timestamp",
            name="key",
            field=models.CharField(
                choices=_TIMESTAMP_KEY_CHOICES, db_index=True, max_length=2
            ),
        ),
    ]
