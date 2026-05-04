"""
Reset global ``cache_book`` so the new default takes effect.

Migration 0039's ``backfill_global_reader_defaults`` populated every
null field on each global :class:`SettingsReader` row with the value
from :data:`READER_DEFAULTS`. At that time ``cache_book`` defaulted
to ``True``, so installs that passed through 0039 came out with an
opaque ``True`` baked into the global row even for users who never
toggled the setting.

The default has since flipped to ``False``. Clearing ``cache_book``
on global rows back to ``NULL`` lets the resolution layer read the
current ``READER_DEFAULTS`` value instead of the stale backfill.
Per-scope rows (per-comic / series / folder / story-arc) are
untouched — those represent deliberate per-scope choices.
"""

from django.db import migrations

_GLOBAL_FILTER = {
    "comic__isnull": True,
    "series__isnull": True,
    "folder__isnull": True,
    "story_arc__isnull": True,
}


def reset_global_cache_book(apps, _schema_editor) -> None:
    """Clear ``cache_book`` on global :class:`SettingsReader` rows."""
    settings_reader = apps.get_model("codex", "SettingsReader")
    settings_reader.objects.filter(**_GLOBAL_FILTER).exclude(
        cache_book__isnull=True
    ).update(cache_book=None)


def _noop(_apps, _schema_editor) -> None:
    """Reverse no-op (data migrations stay applied on rollback)."""


class Migration(migrations.Migration):
    """Reset global ``cache_book`` so the new ``False`` default applies."""

    dependencies = [
        ("codex", "0039_metron_age_rating_default_view_and_performance"),
    ]

    operations = [
        migrations.RunPython(reset_global_cache_book, _noop),
    ]
