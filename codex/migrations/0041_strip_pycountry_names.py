"""
Strip outer whitespace from Country / Language name rows.

Targeted clean-up for rows whose ``name`` field was written before
``CleaningStringFieldMixin.get_prep_value`` learned to strip outer
whitespace. Only ``Country`` and ``Language`` matter here: the
serializer-side pycountry cache (``PyCountryField`` /
``CountryField`` / ``LanguageField``) does an exact dict-key
lookup against alpha_2 / alpha_3 codes, which a trailing space
would silently miss.

Other ``CleaningCharField`` consumers (description, summary,
notes, …) are left alone — outer whitespace there is harmless
display-side, and ``UPDATE … SET name = trim(name)`` would touch
every row in the table for no functional gain.
"""

from django.db import migrations
from django.db.models.functions import Trim


def _strip_pycountry_names(apps, _schema_editor) -> None:
    """Trim outer whitespace from Country.name and Language.name rows."""
    # Country / Language are tiny lookup tables (< 250 rows each at
    # the upper bound of pycountry's data), so the no-op cost of
    # ``Trim`` over every row is negligible — cheaper than a regex
    # pre-filter on SQLite.
    for model_name in ("Country", "Language"):
        model = apps.get_model("codex", model_name)
        model.objects.update(name=Trim("name"))


def _noop_reverse(_apps, _schema_editor) -> None:
    """Reverse is a no-op — stripping whitespace is not reversible."""


class Migration(migrations.Migration):
    """Trim Country.name / Language.name."""

    dependencies = [
        ("codex", "0040_librarianstatus_codex_libstat_active_idx"),
    ]

    operations = [
        migrations.RunPython(_strip_pycountry_names, _noop_reverse),
    ]
