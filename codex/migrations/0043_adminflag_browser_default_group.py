"""Add the BROWSER_DEFAULT_GROUP admin flag."""

from django.db import migrations, models

# Sorted alphabetically by code so future additions can keep the
# pattern. Mirrors ``codex.choices.admin.AdminFlagChoices`` plus the
# new ``BG`` entry.
_ADMIN_FLAG_KEY_CHOICES = [
    ("AA", "Anonymous User Age Rating"),
    ("AR", "Age Rating Default"),
    ("AU", "Auto Update"),
    ("BG", "Default View"),
    ("BT", "Banner Text"),
    ("FV", "Folder View"),
    ("IM", "Import Metadata"),
    ("LI", "Lazy Import Metadata"),
    ("NU", "Non Users"),
    ("RG", "Registration"),
    ("ST", "Send Telemetry"),
]
# Mirrors ``SettingsBrowser.top_group``'s model default. The
# ``admin_default_route_for("p")`` helper resolves this to the
# canonical ``/r/0/1`` redirect target — upgrade-day no-op for
# every existing install.
_DEFAULT_BROWSER_DEFAULT_GROUP_VALUE = "p"


def _seed_browser_default_group_flag(apps, _schema_editor) -> None:
    """
    Insert the BG row with the default top-group value.

    ``get_or_create`` so a re-run of the migration (or running it
    against a DB that already had the row) is idempotent.
    """
    admin_flag = apps.get_model("codex", "AdminFlag")
    admin_flag.objects.get_or_create(
        key="BG",
        defaults={
            "on": True,
            "value": _DEFAULT_BROWSER_DEFAULT_GROUP_VALUE,
        },
    )


def _delete_browser_default_group_flag(apps, _schema_editor) -> None:
    """Reverse the seed insert."""
    admin_flag = apps.get_model("codex", "AdminFlag")
    admin_flag.objects.filter(key="BG").delete()


class Migration(migrations.Migration):
    """Add the BROWSER_DEFAULT_GROUP flag and seed its row."""

    dependencies = [
        ("codex", "0042_alter_adminflag_id_alter_agerating_id_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="adminflag",
            name="key",
            field=models.CharField(
                choices=_ADMIN_FLAG_KEY_CHOICES,
                db_index=True,
                max_length=2,
            ),
        ),
        migrations.RunPython(
            _seed_browser_default_group_flag,
            _delete_browser_default_group_flag,
        ),
    ]
