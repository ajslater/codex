# Generated for age-filter branch.
"""
Introduce :class:`AgeRatingMetron` and rework :class:`AgeRating`.

- Creates ``AgeRatingMetron`` — a fully-seeded canonical lookup table
  (one row per :class:`MetronAgeRatingEnum` value).
- Adds ``AgeRating.metron`` FK (``SET_NULL``) and backfills it from each
  row's ``name`` via comicbox's ``to_metron_age_rating()``.
- Adds ``GroupAuth.age_rating_metron`` for admin-facing age restrictions.
- Renames ``SettingsBrowserFilters.age_rating`` to ``age_rating_tagged``
  and adds the parallel ``age_rating_metron`` JSON column (stores PKs
  of :class:`AgeRatingMetron` rows now — prior scheme stored metron
  name strings; this scheme was never released).
- Registers the new ``AR`` (``AGE_RATING_DEFAULT``) admin flag and seeds
  it with ``Adult`` (most-secure default).

Rebuild the ComicFTS virtual table with the new age-rating columns.

Adds ``age_rating_tagged`` (original tagged name) and ``age_rating_metron``
(normalized Metron value) as first-class FTS columns — replacing the single
``age_rating`` column from 0029. ``ComicFTS`` is unmanaged; its Django state
only tracks ``comic`` + timestamps, so the full column list is owned by
SQL. The search index will be repopulated on the next librarian sync.
"""

from comicbox.enums.maps.age_rating import to_metron_age_rating
from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.db import migrations, models

import codex.models.fields

_AR_FLAG_KEY = "AR"
_DEFAULT_RATING = MetronAgeRatingEnum.ADULT.value
_CHUNK = 500

_METRON_RATING_ORDER = (
    MetronAgeRatingEnum.EVERYONE.value,
    MetronAgeRatingEnum.TEEN.value,
    MetronAgeRatingEnum.TEEN_PLUS.value,
    MetronAgeRatingEnum.MATURE.value,
    MetronAgeRatingEnum.EXPLICIT.value,
    MetronAgeRatingEnum.ADULT.value,
)
_UNRANKED = -1
# ``Unknown`` first (index sentinel), then ranked ratings at 0..5.
_ALL_METRON_RATINGS = (
    (MetronAgeRatingEnum.UNKNOWN.value, _UNRANKED),
    *tuple((name, idx) for idx, name in enumerate(_METRON_RATING_ORDER)),
)
_NEW_FTS_SQL = (
    "CREATE VIRTUAL TABLE codex_comicfts USING fts5("
    "comic_id UNINDEXED, created_at UNINDEXED, updated_at UNINDEXED, "
    "publisher, imprint, series, name, collection_title, "
    "age_rating_tagged, age_rating_metron, country, language, "
    "original_format, review, scan_info, summary, tagger, characters, "
    "credits, genres, locations, roles, series_groups, stories, "
    "story_arcs, tags, teams, universes, sources"
    ")"
)


def _compute_metron_name_for(name):
    """Map an ``AgeRating.name`` to its canonical Metron rating name (or ``""``)."""
    if not name:
        return ""
    result = to_metron_age_rating(name)
    if result is None:
        return ""
    return result.value


def _seed_age_rating_metron(apps, _schema_editor) -> None:
    """Populate :class:`AgeRatingMetron` with every :class:`MetronAgeRatingEnum` value."""
    metron_model = apps.get_model("codex", "ageratingmetron")
    for name, index in _ALL_METRON_RATINGS:
        metron_model.objects.update_or_create(name=name, defaults={"index": index})


def _backfill_age_rating_metron_fk(apps, _schema_editor) -> None:
    """Link each :class:`AgeRating` row to its matching :class:`AgeRatingMetron` row."""
    age_rating_model = apps.get_model("codex", "agerating")
    metron_model = apps.get_model("codex", "ageratingmetron")

    # Cache name → pk for the 7 canonical rows.
    name_to_pk = dict(metron_model.objects.values_list("name", "pk"))

    qs = age_rating_model.objects.only("pk", "name")
    to_update = []
    for age_rating in qs.iterator(chunk_size=_CHUNK):
        metron_name = _compute_metron_name_for(age_rating.name)
        metron_pk = name_to_pk.get(metron_name) if metron_name else None
        age_rating.metron_id = metron_pk
        to_update.append(age_rating)
    if to_update:
        age_rating_model.objects.bulk_update(
            to_update, ["metron_id"], batch_size=_CHUNK
        )


def _seed_age_rating_default_flag(apps, _schema_editor) -> None:
    """Seed AGE_RATING_DEFAULT flag with Adult (most-secure default)."""
    admin_flag_model = apps.get_model("codex", "adminflag")
    flag, _created = admin_flag_model.objects.get_or_create(
        key=_AR_FLAG_KEY,
        defaults={"value": _DEFAULT_RATING},
    )
    if not flag.value:
        # Upgrade case: row pre-seeded by app init with value="".
        flag.value = _DEFAULT_RATING
        flag.save(update_fields=["value"])


def _noop(_apps, _schema_editor) -> None:
    """Reverse no-op (data migrations stay applied on rollback)."""


class Migration(migrations.Migration):
    """Metron-normalised age-rating data model."""

    dependencies = [
        ("codex", "0038_settings_tables"),
    ]

    operations = [
        # Create the canonical Metron lookup table.
        migrations.CreateModel(
            name="AgeRatingMetron",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    codex.models.fields.CleaningCharField(
                        db_index=True, max_length=128
                    ),
                ),
                (
                    "index",
                    models.IntegerField(db_index=True, default=_UNRANKED),
                ),
            ],
            options={
                "get_latest_by": "updated_at",
                "ordering": ("index",),
                "abstract": False,
                "unique_together": {("name",)},
            },
        ),
        # Seed the lookup table before any FK points at it.
        migrations.RunPython(_seed_age_rating_metron, _noop),
        # AgeRating: FK to AgeRatingMetron (nullable, SET_NULL).
        migrations.AddField(
            model_name="agerating",
            name="metron",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                default=None,
                null=True,
                on_delete=models.deletion.SET_NULL,
                to="codex.ageratingmetron",
            ),
        ),
        # Link existing AgeRating rows to their AgeRatingMetron rows.
        migrations.RunPython(_backfill_age_rating_metron_fk, _noop),
        # GroupAuth: per-group Metron age restriction
        migrations.AddField(
            model_name="groupauth",
            name="age_rating_metron",
            field=codex.models.fields.CleaningCharField(
                blank=True,
                choices=[
                    ("Unknown", "Unknown"),
                    ("Everyone", "Everyone"),
                    ("Teen", "Teen"),
                    ("Teen Plus", "Teen Plus"),
                    ("Mature", "Mature"),
                    ("Explicit", "Explicit"),
                    ("Adult", "Adult"),
                ],
                db_collation="nocase",
                db_index=True,
                default=None,
                max_length=9,
                null=True,
            ),
        ),
        # SettingsBrowserFilters: rename tagged filter, add metron filter
        migrations.RenameField(
            model_name="settingsbrowserfilters",
            old_name="age_rating",
            new_name="age_rating_tagged",
        ),
        migrations.AddField(
            model_name="settingsbrowserfilters",
            name="age_rating_metron",
            field=models.JSONField(default=list),
        ),
        # AdminFlag: register the AGE_RATING_DEFAULT (``AR``) key
        migrations.AlterField(
            model_name="adminflag",
            name="key",
            field=models.CharField(
                choices=[
                    ("AR", "Age Rating Default"),
                    ("AU", "Auto Update"),
                    ("BT", "Banner Text"),
                    ("FV", "Folder View"),
                    ("IM", "Import Metadata"),
                    ("LI", "Lazy Import Metadata"),
                    ("NU", "Non Users"),
                    ("RG", "Registration"),
                    ("ST", "Send Telemetry"),
                ],
                db_index=True,
                max_length=2,
            ),
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS codex_comicfts;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=_NEW_FTS_SQL,
            reverse_sql="DROP TABLE IF EXISTS codex_comicfts;",
        ),
        # Seed AdminFlag after its key choices registration.
        migrations.RunPython(_seed_age_rating_default_flag, _noop),
        # ComicFTS is unmanaged; its Django state tracks only (comic,
        # created_at, updated_at). The FTS columns are a SQL-level concern —
        # no state_operations are needed, only a raw DROP + CREATE.
    ]
