"""
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

from django.db import migrations, models


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


def _noop(_apps, _schema_editor) -> None:
    """Reverse no-op — dropping the field drops the data."""


class Migration(migrations.Migration):
    """Add Comic.age_rating_metron_index + composite index + backfill."""

    dependencies = [
        ("codex", "0040_adminflag_age_rating_metron"),
    ]

    operations = [
        migrations.AddField(
            model_name="comic",
            name="age_rating_metron_index",
            field=models.IntegerField(default=None, null=True),
        ),
        migrations.AddIndex(
            model_name="comic",
            index=models.Index(
                fields=("library", "age_rating_metron_index"),
                name="codex_comic_lib_ari_idx",
            ),
        ),
        migrations.RunPython(_backfill_age_rating_metron_index, _noop),
    ]
