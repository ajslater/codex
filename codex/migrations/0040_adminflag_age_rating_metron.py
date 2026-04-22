"""
Typed FK from :class:`AdminFlag` to :class:`AgeRatingMetron`.

Replaces the string-based ``AdminFlag.value`` coupling for the two
age-rating flags (``AGE_RATING_DEFAULT`` / ``AR`` and
``ANONYMOUS_USER_AGE_RATING`` / ``AA``) with a real foreign key. The
ACL filter collapses from a two-level ``name``-matching subquery to a
single FK hop, and the frontend can reuse the live
:class:`AgeRatingMetron` list instead of a parallel static choices JSON.

The data migration resolves each flag's old ``value`` string against
:attr:`AgeRatingMetron.name` and writes the matching row's pk into the
new FK column. Rows whose ``value`` doesn't match any metron name
(shouldn't happen in practice — both flags are seeded with canonical
values by 0039 and the startup seeder) are left with a NULL FK, which
the ACL filter treats as unrestricted / safest default.

The ``value`` column is cleared for ``AR``/``AA`` rows after a
successful backfill so the FK is the single source of truth. Other
flags (``BT``, etc.) keep their ``value`` strings untouched.
"""

import django.db.models.deletion
from django.db import migrations, models

_AGE_RATING_FLAG_KEYS = ("AR", "AA")


def _backfill_age_rating_metron_fk(apps, _schema_editor) -> None:
    """Resolve ``value`` -> ``AgeRatingMetron`` row for AR/AA flag rows."""
    admin_flag_model = apps.get_model("codex", "adminflag")
    metron_model = apps.get_model("codex", "ageratingmetron")

    name_to_pk = dict(metron_model.objects.values_list("name", "pk"))

    flags = admin_flag_model.objects.filter(key__in=_AGE_RATING_FLAG_KEYS)
    to_update = []
    for flag in flags:
        metron_pk = name_to_pk.get(flag.value) if flag.value else None
        flag.age_rating_metron_id = metron_pk
        # The FK is the new source of truth; ``value`` stays empty for
        # these keys so nothing reads a stale string by accident.
        flag.value = ""
        to_update.append(flag)
    if to_update:
        admin_flag_model.objects.bulk_update(
            to_update, ["age_rating_metron_id", "value"]
        )


def _noop(_apps, _schema_editor) -> None:
    """Reverse no-op (data migrations stay applied on rollback)."""


class Migration(migrations.Migration):
    """Add ``AdminFlag.age_rating_metron`` FK and backfill AR/AA rows."""

    dependencies = [
        ("codex", "0039_metron_age_rating"),
    ]

    operations = [
        migrations.AddField(
            model_name="adminflag",
            name="age_rating_metron",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="codex.ageratingmetron",
            ),
        ),
        migrations.RunPython(_backfill_age_rating_metron_fk, _noop),
    ]
