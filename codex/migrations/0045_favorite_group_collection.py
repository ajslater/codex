"""Flip Favorite.group from legacy single-char codes to collection values."""

from django.db import migrations, models

# Legacy single-char favorite group code → v4 collection value.
_CHAR_TO_COLLECTION = {
    "p": "publishers",
    "i": "imprints",
    "s": "series",
    "v": "volumes",
    "f": "folders",
    "a": "arcs",
    "c": "comics",
}
_COLLECTION_TO_CHAR = {
    collection: char for char, collection in _CHAR_TO_COLLECTION.items()
}

# Held inline (not imported from the live model) so the migration keeps
# describing its own historical state across future vocabulary changes.
_FAVORITE_GROUP_CHOICES = [
    ("publishers", "Publishers"),
    ("imprints", "Imprints"),
    ("series", "Series"),
    ("volumes", "Volumes"),
    ("folders", "Folders"),
    ("arcs", "Story Arcs"),
    ("comics", "Issues"),
]


def _char_to_collection(apps, _schema_editor):
    """Rewrite each char-coded favorite group to its collection value."""
    favorite = apps.get_model("codex", "Favorite")
    for char, collection in _CHAR_TO_COLLECTION.items():
        favorite.objects.filter(group=char).update(group=collection)


def _collection_to_char(apps, _schema_editor):
    """Reverse: rewrite collection values back to their char codes."""
    favorite = apps.get_model("codex", "Favorite")
    for collection, char in _COLLECTION_TO_CHAR.items():
        favorite.objects.filter(group=collection).update(group=char)


class Migration(migrations.Migration):
    """Widen Favorite.group and migrate char codes → collection values."""

    dependencies = [("codex", "0044_group_collection_values")]

    operations = [
        # Widen the column and adopt the collection choices before the
        # data move so the longer values fit. Forward runs the alter then
        # the data rewrite; reverse runs the data rewrite (collection →
        # char) then narrows the column back — both keep data and column
        # width consistent at every step.
        migrations.AlterField(
            model_name="favorite",
            name="group",
            field=models.CharField(choices=_FAVORITE_GROUP_CHOICES, max_length=16),
        ),
        migrations.RunPython(_char_to_collection, _collection_to_char),
    ]
