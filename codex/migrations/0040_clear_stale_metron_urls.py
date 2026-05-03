"""
Clear stale Metron URLs that always 404.

Comicbox previously emitted metron.cloud URLs for identifier types
(genre, location, story, tag, creditrole) that have no public web page on
metron.cloud — only API endpoints. Those URLs always return 404. Drop them
from existing rows; re-import will repopulate the URL where applicable
(e.g. roles will pick up the creator URL via comicbox's computed step).
"""

from django.db import migrations

_METRON_SOURCE = "metron"
_UNSUPPORTED_ID_TYPES = ("genre", "location", "story", "tag", "creditrole")


def _clear_stale_metron_urls(apps, _schema_editor) -> None:
    identifier_model = apps.get_model("codex", "identifier")
    qs = identifier_model.objects.filter(
        source__name=_METRON_SOURCE,
        id_type__in=_UNSUPPORTED_ID_TYPES,
    ).exclude(url="")
    count = qs.update(url="")
    if count:
        print(f"\tCleared {count} stale Metron URLs that 404.")


class Migration(migrations.Migration):
    """Clear stale Metron identifier URLs."""

    dependencies = [
        ("codex", "0039_metron_age_rating_default_view_and_performance"),
    ]

    operations = [
        migrations.RunPython(_clear_stale_metron_urls, migrations.RunPython.noop),
    ]
