"""
Flip persisted browser-settings group values from char codes to collections.

Phase 2 of the group→collection unification: the ``Group`` enum's member
*values* became the v4 collection names, so the persisted browser settings
follow. This:

* renames the ``SettingsBrowserShow`` ``p/i/s/v`` boolean columns to
  ``publishers/imprints/series/volumes`` (schema only — values unchanged);
* widens + data-migrates ``SettingsBrowser.top_group`` and
  ``SettingsBrowserLastRoute.group`` from the single-char codes to the
  collection names; and
* strips the dummy ``0`` root sentinel from ``SettingsBrowserLastRoute.pks``.

Reversible: the schema reverts and the data is mapped back to chars (the
stripped root ``0`` is not restored — root is simply the empty list).
"""

from django.db import migrations, models

_CHAR_TO_COLLECTION = {
    "r": "root",
    "p": "publishers",
    "i": "imprints",
    "s": "series",
    "v": "volumes",
    "c": "comics",
    "f": "folders",
    "a": "arcs",
}
_COLLECTION_TO_CHAR = {value: key for key, value in _CHAR_TO_COLLECTION.items()}

_TOP_GROUP_COLLECTION_CHOICES = [
    ("publishers", "Publishers"),
    ("imprints", "Imprints"),
    ("series", "Series"),
    ("volumes", "Volumes"),
    ("comics", "Issues"),
    ("folders", "Folders"),
    ("arcs", "Story Arcs"),
]
_ROUTE_COLLECTION_CHOICES = [*_TOP_GROUP_COLLECTION_CHOICES, ("root", "Root")]


def _migrate_top_group(model, value_map) -> None:
    """Remap ``SettingsBrowser.top_group`` through ``value_map``."""
    for row in model.objects.all().iterator():
        mapped = value_map.get(row.top_group)
        if mapped and mapped != row.top_group:
            row.top_group = mapped
            row.save(update_fields=["top_group"])


def _migrate_last_route_row(row, value_map, *, to_collection: bool) -> None:
    """Remap one last-route row's group + strip the root 0 (forward only)."""
    update_fields = []
    mapped = value_map.get(row.group)
    if mapped not in (None, row.group):
        row.group = mapped
        update_fields.append("group")
    # Purge the dummy 0 root sentinel going forward; root is the empty list.
    stripped = [pk for pk in (row.pks or []) if pk]
    if to_collection and stripped != list(row.pks or []):
        row.pks = stripped
        update_fields.append("pks")
    if update_fields:
        row.save(update_fields=update_fields)


def _migrate_last_route(model, value_map, *, to_collection: bool) -> None:
    """Remap ``SettingsBrowserLastRoute.group`` and strip the root 0 forward."""
    for row in model.objects.all().iterator():
        _migrate_last_route_row(row, value_map, to_collection=to_collection)


def _migrate_values(apps, *, to_collection: bool) -> None:
    """Map stored group chars ↔ collection names (+ strip the root 0)."""
    value_map = _CHAR_TO_COLLECTION if to_collection else _COLLECTION_TO_CHAR
    _migrate_top_group(apps.get_model("codex", "SettingsBrowser"), value_map)
    _migrate_last_route(
        apps.get_model("codex", "SettingsBrowserLastRoute"),
        value_map,
        to_collection=to_collection,
    )


def _forward(apps, schema_editor):  # noqa: ARG001
    """Map stored group chars → collection names."""
    _migrate_values(apps, to_collection=True)


def _reverse(apps, schema_editor):  # noqa: ARG001
    """Map stored collection names → group chars."""
    _migrate_values(apps, to_collection=False)


class Migration(migrations.Migration):
    """Char→collection value flip for persisted browser settings."""

    dependencies = (("codex", "0043_comicbox_tagging_defaults"),)

    operations = (
        # ── SettingsBrowserShow: rename the four flag columns ──
        migrations.RemoveConstraint(
            model_name="settingsbrowsershow",
            name="unique_settingsbrowsershow_flags",
        ),
        migrations.RenameField(
            model_name="settingsbrowsershow", old_name="p", new_name="publishers"
        ),
        migrations.RenameField(
            model_name="settingsbrowsershow", old_name="i", new_name="imprints"
        ),
        migrations.RenameField(
            model_name="settingsbrowsershow", old_name="s", new_name="series"
        ),
        migrations.RenameField(
            model_name="settingsbrowsershow", old_name="v", new_name="volumes"
        ),
        migrations.AddConstraint(
            model_name="settingsbrowsershow",
            constraint=models.UniqueConstraint(
                fields=("publishers", "imprints", "series", "volumes"),
                name="unique_settingsbrowsershow_flags",
            ),
        ),
        # ── Widen the char columns before writing collection names ──
        migrations.AlterField(
            model_name="settingsbrowser",
            name="top_group",
            field=models.CharField(
                choices=_TOP_GROUP_COLLECTION_CHOICES,
                default="publishers",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="settingsbrowserlastroute",
            name="group",
            field=models.CharField(
                choices=_ROUTE_COLLECTION_CHOICES, default="root", max_length=32
            ),
        ),
        # ── Data: char → collection (+ strip root 0) ──
        migrations.RunPython(_forward, _reverse),
    )
