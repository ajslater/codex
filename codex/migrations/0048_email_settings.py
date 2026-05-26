"""Email settings singleton — backs the Admin UI Email tab."""

import django.db.migrations.operations.special
from django.db import migrations, models

import codex.models.fields


def seed_settings(apps, _schema_editor):
    """Create the singleton row with model defaults (blank SMTP config)."""
    EmailSettings = apps.get_model("codex", "EmailSettings")
    EmailSettings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    """Create EmailSettings model + seed singleton."""

    dependencies = [
        ("codex", "0047_drop_library_covers_only"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("host", models.CharField(blank=True, default="", max_length=128)),
                ("port", models.PositiveSmallIntegerField(default=587)),
                ("user", models.CharField(blank=True, default="", max_length=128)),
                (
                    "password",
                    codex.models.fields.EncryptedCharField(
                        blank=True, default="", max_length=512
                    ),
                ),
                ("use_tls", models.BooleanField(default=True)),
                ("use_ssl", models.BooleanField(default=False)),
                ("timeout", models.PositiveSmallIntegerField(default=10)),
                (
                    "from_address",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "subject_prefix",
                    models.CharField(blank=True, default="[Codex] ", max_length=32),
                ),
            ],
            options={
                "verbose_name_plural": "EmailSettings",
                "abstract": False,
                "get_latest_by": "updated_at",
            },
        ),
        migrations.RunPython(
            code=seed_settings,
            reverse_code=django.db.migrations.operations.special.RunPython.noop,
        ),
    ]
