"""
Drop the tagging-session columns from ``ComicboxTaggingDefaults``.

``active_session_id`` and ``active_prompts`` were transient operational
state for an in-flight online tagging job. Mixing them with the
singleton row's persistent configuration (default match mode, source
credentials, etc.) muddled the table's purpose and meant clearing
session state on daemon shutdown / cleanup also touched config rows.

The two fields moved to the Django cache. See
``codex.librarian.onlinetag.session_state``.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove active_session_id and active_prompts."""

    dependencies = [
        ("codex", "0052_timestamp_value"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="comicboxtaggingdefaults",
            name="active_session_id",
        ),
        migrations.RemoveField(
            model_name="comicboxtaggingdefaults",
            name="active_prompts",
        ),
    ]
