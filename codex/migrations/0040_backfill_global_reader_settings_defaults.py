"""Backfill user-facing defaults onto existing global reader settings rows."""

from django.db import migrations

from codex.choices.reader import READER_DEFAULTS

_GLOBAL_FILTER = {
    "comic__isnull": True,
    "series__isnull": True,
    "folder__isnull": True,
    "story_arc__isnull": True,
}
_NULL_VALUES = frozenset({None, ""})


def backfill_global_reader_defaults(apps, _schema_editor) -> None:
    """
    Populate null/blank fields on global SettingsReader rows with READER_DEFAULTS.

    Earlier versions created the global reader settings row with model field
    defaults ("" / None), which the UI rendered as empty controls. New rows
    are now seeded with READER_DEFAULTS at creation; this migration brings
    pre-existing rows up to the same shape without disturbing values the
    user has explicitly set.
    """
    settings_reader = apps.get_model("codex", "SettingsReader")
    rows = settings_reader.objects.filter(**_GLOBAL_FILTER)
    updated = []
    for row in rows:
        dirty = False
        for key, default in READER_DEFAULTS.items():
            if getattr(row, key) in _NULL_VALUES:
                setattr(row, key, default)
                dirty = True
        if dirty:
            updated.append(row)
    if updated:
        settings_reader.objects.bulk_update(updated, list(READER_DEFAULTS.keys()))


class Migration(migrations.Migration):
    """Backfill global reader settings rows with user-facing defaults."""

    dependencies = [
        ("codex", "0039_metron_age_rating_default_view_and_performance"),
    ]

    operations = [
        migrations.RunPython(
            backfill_global_reader_defaults,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
