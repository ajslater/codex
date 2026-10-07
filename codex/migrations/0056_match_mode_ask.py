"""
Online tagging's match mode gains comicbox's ``ask``.

Ask auto-writes nothing and prompts for every match. comicbox 5.3.1 accepts
it from a session with a prompt handler, which codex always supplies, so the
choices now come from comicbox's enum instead of a hand-written copy. The
column itself is unchanged; only the choices Django validates against grow.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add ask to the match mode choices."""

    dependencies = [
        ("codex", "0055_settings_defaults"),
    ]

    operations = [
        migrations.AlterField(
            model_name="comicboxtaggingdefaults",
            name="default_match_mode",
            field=models.CharField(
                choices=[
                    ("ask", "Ask"),
                    ("careful", "Careful"),
                    ("auto", "Auto"),
                    ("eager", "Eager"),
                ],
                default="auto",
                max_length=32,
            ),
        ),
    ]
