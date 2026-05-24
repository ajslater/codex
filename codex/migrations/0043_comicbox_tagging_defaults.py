"""Add ComicboxTaggingDefaults singleton model."""

from django.db import migrations, models

import codex.models.fields


def seed_defaults(apps, _schema_editor):
    """Create the singleton defaults row."""
    ComicboxTaggingDefaults = apps.get_model("codex", "ComicboxTaggingDefaults")
    ComicboxTaggingDefaults.objects.get_or_create(
        pk=1,
        defaults={
            "default_formats": ["COMIC_INFO"],
            "default_sources": ["metron", "comicvine"],
        },
    )


class Migration(migrations.Migration):
    """Create the ComicboxTaggingDefaults singleton model."""

    dependencies = [
        ("codex", "0042_browser_table_view_and_favorites"),
    ]

    operations = [
        migrations.CreateModel(
            name="ComicboxTaggingDefaults",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "default_formats",
                    models.JSONField(default=list),
                ),
                (
                    "default_match_mode",
                    models.CharField(
                        choices=[
                            ("strict", "Strict"),
                            ("normal", "Normal"),
                            ("fast", "Fast"),
                        ],
                        default="normal",
                        max_length=32,
                    ),
                ),
                (
                    "default_prompts_mode",
                    models.CharField(
                        choices=[
                            ("ask", "Ask"),
                            ("never", "Never"),
                        ],
                        default="ask",
                        max_length=32,
                    ),
                ),
                (
                    "default_sources",
                    models.JSONField(default=list),
                ),
                (
                    "prompt_timeout_seconds",
                    models.IntegerField(default=3600),
                ),
                (
                    "metron_user",
                    codex.models.fields.EncryptedCharField(
                        blank=True, default="", max_length=512
                    ),
                ),
                (
                    "metron_password",
                    codex.models.fields.EncryptedCharField(
                        blank=True, default="", max_length=512
                    ),
                ),
                (
                    "metron_url",
                    models.URLField(blank=True, default="", max_length=256),
                ),
                (
                    "comicvine_key",
                    codex.models.fields.EncryptedCharField(
                        blank=True, default="", max_length=512
                    ),
                ),
                (
                    "comicvine_url",
                    models.URLField(blank=True, default="", max_length=256),
                ),
                (
                    "active_session_id",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "active_prompts",
                    models.JSONField(default=list),
                ),
            ],
            options={
                "verbose_name_plural": "ComicboxTaggingDefaults",
                "abstract": False,
                "get_latest_by": "updated_at",
            },
        ),
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]
