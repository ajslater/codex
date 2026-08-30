"""
Merge the Alternate Number sort into Alternate Series.

The two sorts each did half the job — ``reprints`` ordered by a display
label (so "#10" preceded "#2") and ``alternate_number`` ordered by the
parsed number but ignored which alternate series it belonged to. They
are now one key, ``reprints``.

0053 dropped ``alternate_number`` from the field's choices, but choices
aren't enforced by SQLite and 0053 has already been applied on every
database that could hold the value, so the stored settings need this
separate pass. Left in place, a stale key reaches ORDER BY unvalidated
(settings load raw) and raises FieldError.

The key lives in three places on SettingsBrowser — the ``order_by``
column, the ``order_extra_keys`` list, and the per-top-collection
``collection_order_memory`` map — and saved views are more rows in the
same table, so every row is remapped regardless of name or client.
"""

from django.db import migrations

_OLD_KEY = "alternate_number"
_NEW_KEY = "reprints"


def _remap_extra_keys(entries) -> tuple[list, bool]:
    """Remap the sort key in an extras list, dropping a duplicate."""
    if not isinstance(entries, list):
        return entries, False
    remapped: list = []
    changed = False
    seen: set = set()
    for entry in entries:
        key = entry.get("key") if isinstance(entry, dict) else None
        if key == _OLD_KEY:
            entry = {**entry, "key": _NEW_KEY}  # noqa: PLW2901
            key = _NEW_KEY
            changed = True
        if key in seen:
            # The row already sorted by the surviving key. Two entries
            # for one column is not a state the sort can express, so the
            # first occurrence wins, as the serializer's own extras
            # cleaner does.
            changed = True
            continue
        seen.add(key)
        remapped.append(entry)
    return remapped, changed


def _remap_memory(memory) -> tuple[dict, bool]:
    """Remap the sort key inside a collection_order_memory map."""
    if not isinstance(memory, dict):
        return memory, False
    changed = False
    for remembered in memory.values():
        if not isinstance(remembered, dict):
            continue
        if remembered.get("order_by") == _OLD_KEY:
            remembered["order_by"] = _NEW_KEY
            changed = True
        extras, extras_changed = _remap_extra_keys(remembered.get("order_extra_keys"))
        if extras_changed:
            remembered["order_extra_keys"] = extras
            changed = True
    return memory, changed


def _remap_browser_settings(apps, _schema_editor) -> None:
    settings_browser = apps.get_model("codex", "SettingsBrowser")
    settings_browser.objects.filter(order_by=_OLD_KEY).update(order_by=_NEW_KEY)
    # JSON payloads need a python pass; JSONField key lookups are
    # unsupported on SQLite, so scan and rewrite sparsely.
    rows = []
    for row in settings_browser.objects.only(
        "pk", "order_extra_keys", "collection_order_memory"
    ):
        extras, extras_changed = _remap_extra_keys(row.order_extra_keys)
        memory, memory_changed = _remap_memory(row.collection_order_memory)
        if extras_changed or memory_changed:
            row.order_extra_keys = extras
            row.collection_order_memory = memory
            rows.append(row)
    if rows:
        settings_browser.objects.bulk_update(
            rows, ["order_extra_keys", "collection_order_memory"]
        )


class Migration(migrations.Migration):
    """Remap the retired alternate_number sort key onto reprints."""

    dependencies = [
        ("codex", "0053_reprint_issue_number_and_collection_order_memory"),
    ]

    operations = [
        # Irreversible by design: both former keys map onto ``reprints``,
        # so a reverse pass can't know which rows to send back.
        migrations.RunPython(_remap_browser_settings, migrations.RunPython.noop),
    ]
