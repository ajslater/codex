# Generated for age-filter branch.
"""
Introduce :class:`AgeRatingMetron` and per-user age-rating ACL.

- Creates ``AgeRatingMetron`` — a fully-seeded canonical lookup table
  (one row per :class:`MetronAgeRatingEnum` value).
- Adds ``AgeRating.metron`` FK (``SET_NULL``) and backfills it from each
  row's ``name`` via comicbox's ``to_metron_age_rating()``.
- Renames ``UserActive`` → ``UserAuth`` and adds ``UserAuth.age_rating_metron``
  FK (``SET_NULL``, nullable) — the per-user age-rating ceiling (null =
  unrestricted).
- Renames ``SettingsBrowserFilters.age_rating`` to ``age_rating_tagged``
  and adds the parallel ``age_rating_metron`` JSON column (stores PKs
  of :class:`AgeRatingMetron` rows now — prior scheme stored metron
  name strings; this scheme was never released).
- Registers the ``AR`` (``AGE_RATING_DEFAULT``) admin flag seeded with
  ``Everyone`` (safe null-rating inheritance) and the new ``AA``
  (``ANONYMOUS_USER_AGE_RATING``) admin flag seeded with ``Adult``
  (out-of-the-box anonymous browsing sees the full library).

Rebuild the ComicFTS virtual table with the new age-rating columns.

Adds ``age_rating_tagged`` (original tagged name) and ``age_rating_metron``
(normalized Metron value) as first-class FTS columns — replacing the single
``age_rating`` column from 0029. ``ComicFTS`` is unmanaged; its Django state
only tracks ``comic`` + timestamps, so the full column list is owned by
SQL. The search index will be repopulated on the next librarian sync.

----

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

---

Denormalize :attr:`Comic.age_rating_metron_index` for the ACL filter.

Adds a nullable integer column on :class:`Comic` that mirrors
:attr:`Comic.age_rating.metron.index`. The ACL age-rating filter in
:mod:`codex.views.auth` compares this column directly, so the whole
filter collapses from a two-hop join
(``comic → age_rating → metron``) to a single local-column predicate.
Combined with the composite index on ``(library_id,
age_rating_metron_index)`` added here, the filter becomes
index-only.

Semantics encoded by the column value:

* ``NULL`` — the comic has no ``age_rating`` FK, or its
  :class:`AgeRating` row failed to map to a canonical
  :class:`AgeRatingMetron`. ACL-wise, handled by the
  ``AGE_RATING_DEFAULT`` flag fallback path.
* ``-1`` (``UNRANKED_METRON_INDEX``) — the comic is tagged ``Unknown``;
  same fallback path as ``NULL``.
* ``0``..``5`` — ranked rating; compared directly against the user's
  ceiling.

The backfill runs as a single correlated SQL ``UPDATE`` scoped to rows
with ``age_rating_id IS NOT NULL``. On a 600k-row library this is
~10-20 seconds dominated by WAL fsync - acceptable as a one-shot
migration. Going forward, :meth:`Comic.presave` keeps the column in
sync on every bulk insert/update the importer performs.

``SET NULL`` on delete cascades for the upstream :class:`AgeRatingMetron`
FK mean the denorm can fall out of sync only when an
:class:`AgeRating` row has its :attr:`metron` relinked — which already
happens inside :meth:`AgeRating.presave`, and any
:class:`Comic` that references that AgeRating will be re-saved on
re-import. For the rare "comicbox enum got updated" case, a fresh
library rescan walks every affected Comic through
:meth:`Comic.presave` and heals the drift.
"""

from comicbox.enums.maps.age_rating import to_metron_age_rating
from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.db import migrations, models
from django.db.models.deletion import SET_NULL
from django.db.models.functions import Trim

import codex.models.fields

_AR_FLAG_KEY = "AR"
_AR_DEFAULT = MetronAgeRatingEnum.EVERYONE.value
_AA_FLAG_KEY = "AA"
_AA_DEFAULT = MetronAgeRatingEnum.ADULT.value
_AGE_RATING_FLAG_KEYS = (_AR_FLAG_KEY, _AA_FLAG_KEY)
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
# Sorted alphabetically by code so future additions can keep the
# pattern. Mirrors ``codex.choices.admin.AdminFlagChoices`` plus the
# new ``BG`` entry.
_ADMIN_FLAG_KEY_CHOICES = [
    ("AA", "Anonymous User Age Rating"),
    ("AR", "Age Rating Default"),
    ("AU", "Auto Update"),
    ("BT", "Banner Text"),
    ("BG", "Browser Default Group"),
    ("FV", "Folder View"),
    ("IM", "Import Metadata"),
    ("LI", "Lazy Import Metadata"),
    ("NU", "Non Users"),
    ("RG", "Registration"),
    ("ST", "Send Telemetry"),
]
_LIBRARIAN_STATUS_CHOICES = [
    ("CCC", "Create Covers"),
    ("CFO", "Find Orphan Covers"),
    ("CRC", "Remove Covers"),
    ("IAT", "Aggregate Tags From Comics"),
    ("ICC", "Create Comics"),
    ("ICT", "Create Tags"),
    ("ICV", "Create Custom Covers"),
    ("IFC", "Mark Failed Failed Imports"),
    ("IFD", "Clean Up Failed Imports"),
    ("IFQ", "Query Failed Imports"),
    ("IFU", "Update Failed Imports"),
    ("IGU", "Update Timestamps For Browser Groups"),
    ("ILT", "Link Tags"),
    ("ILV", "Link Custom Covers"),
    ("IMC", "Move Comics"),
    ("IMF", "Move Folders"),
    ("IMV", "Move Custom Covers"),
    ("IQC", "Query Comics"),
    ("IQL", "Query Tag Links"),
    ("IQT", "Query Missing Tags"),
    ("IQV", "Query Missing Custom Covers"),
    ("IRC", "Remove Comics"),
    ("IRF", "Remove Folders"),
    ("IRT", "Read Tags From Comics"),
    ("IRV", "Remove Custom Covers"),
    ("ISC", "Create Search Index Entries"),
    ("ISU", "Update Search Index Entries"),
    ("IUC", "Update Comics"),
    ("IUF", "Update Folders"),
    ("IUT", "Update Tags"),
    ("IUV", "Update Custom Covers"),
    ("JAF", "Adopt Orphan Folders"),
    ("JAS", "Cleanup Orphan Settings"),
    ("JCT", "Cleanup Orphan Tags"),
    ("JCU", "Update Codex Server Software"),
    ("JDB", "Backup Database"),
    ("JDO", "Optimize Database"),
    ("JID", "Check Integrity Of Entire Database"),
    ("JIF", "Check Integrtity Of Database Foreign Keys"),
    ("JIS", "Check Integrity Of Full Text Virtual Table"),
    ("JLV", "Check Codex Latest Version"),
    ("JRB", "Cleanup Orphan Bookmarks"),
    ("JRS", "Cleanup Old Sessions"),
    ("JRV", "Cleanup Orphan Covers"),
    ("JSR", "Rebuild Full Text Search Virtual Table"),
    ("RCR", "Restart Codex Server"),
    ("RCS", "Stop Codex Server"),
    ("SIO", "Optimize Search Virtual Table"),
    ("SIR", "Clean Orphan Search Entries"),
    ("SIX", "Clear Full Text Search Table"),
    ("SSC", "Sync New Search Entries"),
    ("SSU", "Sync Old Search Entries"),
    ("WPO", "Poll Library"),
    ("WRS", "Restart File Watcher"),
]
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
# Mirrors ``SettingsBrowser.top_group``'s model default. The
# ``admin_default_route_for("p")`` helper resolves this to the
# canonical ``/r/0/1`` redirect target — upgrade-day no-op for
# every existing install.
_DEFAULT_BROWSER_DEFAULT_GROUP_VALUE = "p"


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


def _backfill_age_rating_metron_flag_fk(apps, _schema_editor) -> None:
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


def _backfill_age_rating_metron_index(_apps, _schema_editor) -> None:
    """
    Populate :attr:`Comic.age_rating_metron_index` for every existing row.

    Runs a single correlated ``UPDATE`` instead of iterating in Python:
    SQLite evaluates the subquery row-by-row using the indexes on
    ``codex_agerating.id`` and ``codex_ageratingmetron.id``, so the
    whole migration is one statement regardless of library size.
    """
    # ``schema_editor`` is the normal way to get at the connection here,
    # but the raw cursor is fine since the statement is pure SQL and we
    # only run it on SQLite.
    from django.db import connection

    with connection.cursor() as cursor:
        # ``index`` is a reserved keyword in SQLite; quote the column
        # reference so the parser treats it as an identifier. The bare
        # column name stored in the table is also ``index`` — Django
        # renders the field definition without quotes because it's fine
        # in DDL, but inside a SELECT expression it needs escaping.
        cursor.execute(
            """
            UPDATE codex_comic
            SET age_rating_metron_index = (
                SELECT arm."index"
                FROM codex_ageratingmetron AS arm
                INNER JOIN codex_agerating AS ar
                    ON ar.metron_id = arm.id
                WHERE ar.id = codex_comic.age_rating_id
            )
            WHERE age_rating_id IS NOT NULL
            """
        )


def _seed_age_rating_default_flag(apps, _schema_editor) -> None:
    """Seed AGE_RATING_DEFAULT flag with Everyone (safest null-rating inheritance)."""
    admin_flag_model = apps.get_model("codex", "adminflag")
    flag, _created = admin_flag_model.objects.get_or_create(
        key=_AR_FLAG_KEY,
        defaults={"value": _AR_DEFAULT},
    )
    if not flag.value:
        # Upgrade case: row pre-seeded by app init with value="".
        flag.value = _AR_DEFAULT
        flag.save(update_fields=["value"])


def _seed_anonymous_user_age_rating_flag(apps, _schema_editor) -> None:
    """Seed ANONYMOUS_USER_AGE_RATING flag with Adult (permissive default)."""
    admin_flag_model = apps.get_model("codex", "adminflag")
    flag, _created = admin_flag_model.objects.get_or_create(
        key=_AA_FLAG_KEY,
        defaults={"value": _AA_DEFAULT},
    )
    if not flag.value:
        flag.value = _AA_DEFAULT
        flag.save(update_fields=["value"])


def _noop(_apps, _schema_editor) -> None:
    """Reverse no-op (data migrations stay applied on rollback)."""


def _strip_pycountry_names(apps, _schema_editor) -> None:
    """Trim outer whitespace from Country.name and Language.name rows."""
    # Country / Language are tiny lookup tables (< 250 rows each at
    # the upper bound of pycountry's data), so the no-op cost of
    # ``Trim`` over every row is negligible — cheaper than a regex
    # pre-filter on SQLite.
    for model_name in ("Country", "Language"):
        model = apps.get_model("codex", model_name)
        model.objects.update(name=Trim("name"))


def _seed_browser_default_group_flag(apps, _schema_editor) -> None:
    """
    Insert the BG row with the default top-group value.

    ``get_or_create`` so a re-run of the migration (or running it
    against a DB that already had the row) is idempotent.
    """
    admin_flag = apps.get_model("codex", "AdminFlag")
    admin_flag.objects.get_or_create(
        key="BG",
        defaults={
            "on": True,
            "value": _DEFAULT_BROWSER_DEFAULT_GROUP_VALUE,
        },
    )


def _delete_browser_default_group_flag(apps, _schema_editor) -> None:
    """Reverse the seed insert."""
    admin_flag = apps.get_model("codex", "AdminFlag")
    admin_flag.objects.filter(key="BG").delete()


class Migration(migrations.Migration):
    """Metron-normalised age-rating data model with per-user ACL."""

    dependencies = [
        ("codex", "0038_settings_tables"),
    ]

    operations = [
        migrations.AlterField(
            model_name="adminflag",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="agerating",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="bookmark",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="character",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="comic",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="country",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="credit",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="creditperson",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="creditrole",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="customcover",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="failedimport",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="folder",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="genre",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="groupauth",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="identifier",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="identifiersource",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="imprint",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="language",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="librarianstatus",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="library",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="location",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="originalformat",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="publisher",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="scaninfo",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="series",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="seriesgroup",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="settingsbrowser",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="settingsbrowserfilters",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="settingsbrowserlastroute",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="settingsbrowsershow",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="settingsreader",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="story",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="storyarc",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="storyarcnumber",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="tag",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="tagger",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="team",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="timestamp",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="universe",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="volume",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        # Create the canonical Metron lookup table.
        migrations.CreateModel(
            name="AgeRatingMetron",
            fields=[
                (
                    "id",
                    models.BigAutoField(
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
        # UserActive → UserAuth rename; then add the per-user ceiling FK.
        migrations.RenameModel(old_name="UserActive", new_name="UserAuth"),
        migrations.AlterField(
            model_name="userauth",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AddField(
            model_name="userauth",
            name="age_rating_metron",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                default=None,
                null=True,
                on_delete=models.deletion.SET_NULL,
                to="codex.ageratingmetron",
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
        # AdminFlag: register the AGE_RATING_DEFAULT (``AR``) and
        # ANONYMOUS_USER_AGE_RATING (``AA``) keys.
        #
        migrations.AlterField(
            model_name="adminflag",
            name="key",
            field=models.CharField(
                choices=_ADMIN_FLAG_KEY_CHOICES, db_index=True, max_length=2
            ),
        ),
        migrations.AddField(
            model_name="adminflag",
            name="age_rating_metron",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                default=None,
                null=True,
                on_delete=SET_NULL,
                to="codex.ageratingmetron",
            ),
        ),
        migrations.AddField(
            model_name="comic",
            name="age_rating_metron_index",
            field=models.IntegerField(default=None, null=True),
        ),
        migrations.AlterField(
            model_name="librarianstatus",
            name="status_type",
            field=models.CharField(
                choices=_LIBRARIAN_STATUS_CHOICES, db_index=True, max_length=3
            ),
        ),
        migrations.AddIndex(
            model_name="librarianstatus",
            index=models.Index(
                condition=models.Q(
                    ("preactive__isnull", False),
                    ("active__isnull", False),
                    _connector="OR",
                ),
                fields=["preactive", "active"],
                name="codex_libstat_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="comic",
            index=models.Index(
                fields=("library", "age_rating_metron_index"),
                name="codex_comic_lib_ari_idx",
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
        # Seed AdminFlag rows after their key choices registration.
        migrations.RunPython(_seed_age_rating_default_flag, _noop),
        migrations.RunPython(_seed_anonymous_user_age_rating_flag, _noop),
        migrations.RunPython(_backfill_age_rating_metron_index, _noop),
        migrations.RunPython(_backfill_age_rating_metron_flag_fk, _noop),
        migrations.RunPython(_strip_pycountry_names, _noop),
        migrations.RunPython(
            _seed_browser_default_group_flag,
            _delete_browser_default_group_flag,
        ),
        # ComicFTS is unmanaged; its Django state tracks only (comic,
        # created_at, updated_at). The FTS columns are a SQL-level concern —
        # no state_operations are needed, only a raw DROP + CREATE.
    ]
