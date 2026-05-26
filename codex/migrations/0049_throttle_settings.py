"""
Throttle settings singleton + import of current TOML/env values.

On first upgrade we copy ``settings.THROTTLE_*`` (sourced from the
TOML/env at boot) into the new DB row so admins do not lose their
existing rate limits when the runtime UI takes over.
"""

import django.db.migrations.operations.special
from django.conf import settings
from django.db import migrations, models


def seed_settings(apps, _schema_editor):
    """Seed the singleton from current TOML/env values."""
    ThrottleSettings = apps.get_model("codex", "ThrottleSettings")
    ThrottleSettings.objects.get_or_create(
        pk=1,
        defaults={
            "anon": getattr(settings, "THROTTLE_ANON", 0) or 0,
            "user": getattr(settings, "THROTTLE_USER", 0) or 0,
            "opds": getattr(settings, "THROTTLE_OPDS", 0) or 0,
            "opensearch": getattr(settings, "THROTTLE_OPENSEARCH", 0) or 0,
            "reset_password": getattr(settings, "THROTTLE_RESET_PASSWORD", 5) or 0,
        },
    )


class Migration(migrations.Migration):
    """Create ThrottleSettings model + seed from current settings."""

    dependencies = [
        ("codex", "0048_email_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="ThrottleSettings",
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
                ("anon", models.PositiveSmallIntegerField(default=0)),
                ("user", models.PositiveSmallIntegerField(default=0)),
                ("opds", models.PositiveSmallIntegerField(default=0)),
                ("opensearch", models.PositiveSmallIntegerField(default=0)),
                ("reset_password", models.PositiveSmallIntegerField(default=5)),
            ],
            options={
                "verbose_name_plural": "ThrottleSettings",
                "abstract": False,
                "get_latest_by": "updated_at",
            },
        ),
        migrations.RunPython(
            code=seed_settings,
            reverse_code=django.db.migrations.operations.special.RunPython.noop,
        ),
    ]
