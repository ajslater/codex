"""Flip CustomCover.group from legacy single-char codes to collection values."""

from django.db import migrations, models

# Legacy single-char custom-cover group code → v4 collection value.
_CHAR_TO_COLLECTION = {
    "p": "publishers",
    "i": "imprints",
    "s": "series",
    "v": "volumes",
    "a": "arcs",
    "f": "folders",
}
_COLLECTION_TO_CHAR = {
    collection: char for char, collection in _CHAR_TO_COLLECTION.items()
}

# Held inline (not imported from the live model) so the migration keeps
# describing its own historical state across future vocabulary changes.
_GROUP_CHOICES = [
    ("publishers", "Publishers"),
    ("imprints", "Imprints"),
    ("series", "Series"),
    ("volumes", "Volumes"),
    ("arcs", "Arcs"),
    ("folders", "Folders"),
]


def _char_to_collection(apps, _schema_editor):
    """Rewrite each char-coded custom-cover group to its collection value."""
    custom_cover = apps.get_model("codex", "CustomCover")
    for char, collection in _CHAR_TO_COLLECTION.items():
        custom_cover.objects.filter(group=char).update(group=collection)


def _collection_to_char(apps, _schema_editor):
    """Reverse: rewrite collection values back to their char codes."""
    custom_cover = apps.get_model("codex", "CustomCover")
    for collection, char in _COLLECTION_TO_CHAR.items():
        custom_cover.objects.filter(group=collection).update(group=char)


class Migration(migrations.Migration):
    """Widen CustomCover.group and migrate char codes → collection values."""

    dependencies = [("codex", "0045_favorite_group_collection")]

    operations = [
        # Widen + adopt collection choices before the data move so the
        # longer values fit; the reverse rewrites data then narrows.
        migrations.AlterField(
            model_name="customcover",
            name="group",
            field=models.CharField(
                choices=_GROUP_CHOICES, db_index=True, max_length=10
            ),
        ),
        migrations.RunPython(_char_to_collection, _collection_to_char),
    ]
