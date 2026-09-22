"""
Everything the schema gained after v2.3.3, as one migration.

v2.3.3 shipped through 0053, so nothing here has reached a release. The three
migrations that landed on develop since are folded together rather than left as
a chain of single-field steps: an upgrading install applies one migration, and
the bookmark dedupe below runs once, before the constraints that need it.

In order:

- **Bookmarks get one row per owner per comic, enforced by the database.**
  ``unique_together = (user, session, comic)`` never enforced anything: both
  owner columns are nullable and SQL treats NULLs in a unique index as
  distinct, so ``(user=1, session=NULL, comic=5)`` could be stored any number
  of times. Duplicates are not cosmetic -- the browser sums ``page`` and
  ``finished`` over the rows, the reader takes whichever it read last, and
  OPDS progression raises ``MultipleObjectsReturned``, which surfaces as a
  500. Existing violations are merged first: the most recently updated row of
  a group survives and takes the group's progress with it, and rows owned by
  neither a user nor a session are deleted as unreachable.
- **``missing_since`` on the four ``WatchedPath`` tables.** A scan that cannot
  find a file used to infer a deletion, which cascaded the comic's bookmarks
  away with it. NULL means present, the correct initial state for every
  existing row, so there is no backfill. Only Comic and Folder get an index,
  and it is partial: the per-request filter is ``missing_since IS NULL``,
  which matches ~every row and no index can serve, while the nightly reap is
  ``missing_since < cutoff``, which matches ~none.
- **``JRP`` joins the librarian status choices** so the pending-delete
  reaper's status row can exist. All the keys are three characters, so the
  column width does not move.

SQLite rolls DDL back and ``Migration.atomic`` is on by default, so the merge
and everything after it land together or not at all. The conditional
``UniqueConstraint``s are ``CREATE UNIQUE INDEX ... WHERE`` and dropping
``unique_together`` is a ``DROP INDEX``, so no table is rebuilt.
"""

from django.conf import settings
from django.db import migrations, models
from django.db.models import Count, F

# Chunk the loser deletes: a pk list becomes one bound parameter per pk.
_BATCH_SIZE = 900
# The most recently updated row wins. In the session pass a row that also
# has a user outranks an anonymous one, so a signed-in reader's row is
# never the one dropped.
_ORDER = {
    "user": ("-updated_at", "-pk"),
    "session": (F("user_id").desc(nulls_last=True), "-updated_at", "-pk"),
}


def _merge_into_winner(rows) -> list[int]:
    """Fold a duplicate group into its first row; return the losers' pks."""
    winner = rows[0]
    finished = any(row.finished for row in rows)
    page = winner.page
    if page is None:
        pages = [row.page for row in rows if row.page is not None]
        page = max(pages) if pages else None
    if finished != winner.finished or page != winner.page:
        winner.finished = finished
        winner.page = page
        winner.save(update_fields=("finished", "page"))
    return [row.pk for row in rows[1:]]


def _dedupe_owner(bookmark_model, owner: str) -> int:
    """Collapse every group of rows one of the new constraints would reject."""
    owner_id = f"{owner}_id"
    groups = (
        bookmark_model.objects.filter(**{f"{owner_id}__isnull": False})
        .values(owner_id, "comic_id")
        .annotate(count=Count("pk"))
        .filter(count__gt=1)
        .order_by()
    )
    loser_pks: list[int] = []
    for group in groups:
        rows = list(
            bookmark_model.objects.filter(
                **{owner_id: group[owner_id], "comic_id": group["comic_id"]}
            ).order_by(*_ORDER[owner])
        )
        loser_pks += _merge_into_winner(rows)
    for start in range(0, len(loser_pks), _BATCH_SIZE):
        bookmark_model.objects.filter(
            pk__in=loser_pks[start : start + _BATCH_SIZE]
        ).delete()
    return len(loser_pks)


def dedupe_bookmarks(apps, _schema_editor) -> None:
    """Make the table satisfy the constraints that follow."""
    bookmark_model = apps.get_model("codex", "Bookmark")
    # The user pass runs first: a row with both owners is bound by both
    # constraints, and merging it as a user row keeps that reader's
    # progress on the row they can actually see.
    merged = {owner: _dedupe_owner(bookmark_model, owner) for owner in _ORDER}
    ownerless, _ = bookmark_model.objects.filter(
        user_id__isnull=True, session_id__isnull=True
    ).delete()
    if not (any(merged.values()) or ownerless):
        return
    print(f"\nBookmarks: merged {merged['user']} duplicate user rows.")
    print(f"Bookmarks: merged {merged['session']} duplicate session rows.")
    print(f"Bookmarks: deleted {ownerless} rows that belonged to nobody.")


class Migration(migrations.Migration):
    """Bookmark uniqueness, missing_since, the reaper status, read state."""

    dependencies = [
        ("codex", "0053_comicbox_5_reprints_and_sort_memory"),
        ("sessions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            dedupe_bookmarks,
            migrations.RunPython.noop,
        ),
        migrations.AlterUniqueTogether(
            name="bookmark",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="bookmark",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", False)),
                fields=("user", "comic"),
                name="unique_bookmark_user_comic",
            ),
        ),
        migrations.AddConstraint(
            model_name="bookmark",
            constraint=models.UniqueConstraint(
                condition=models.Q(("session__isnull", False)),
                fields=("session", "comic"),
                name="unique_bookmark_session_comic",
            ),
        ),
        migrations.AddField(
            model_name="comic",
            name="missing_since",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="customcover",
            name="missing_since",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="failedimport",
            name="missing_since",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="folder",
            name="missing_since",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddIndex(
            model_name="comic",
            index=models.Index(
                condition=models.Q(("missing_since__isnull", False)),
                fields=["missing_since"],
                name="codex_comic_miss_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="folder",
            index=models.Index(
                condition=models.Q(("missing_since__isnull", False)),
                fields=["missing_since"],
                name="codex_folder_miss_idx",
            ),
        ),
        migrations.AlterField(
            model_name="librarianstatus",
            name="status_type",
            field=models.CharField(
                choices=[
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
                    ("IGU", "Update Timestamps For Browser Collections"),
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
                    ("JDU", "Snapshot User Data Sidecar"),
                    ("JFR", "Repair Comic Folder Relations"),
                    ("JID", "Check Integrity Of Entire Database"),
                    ("JIF", "Check Integrity Of Database Foreign Keys"),
                    ("JIS", "Check Integrity Of Full Text Virtual Table"),
                    ("JLV", "Check Codex Latest Version"),
                    ("JRB", "Cleanup Orphan Bookmarks"),
                    ("JRF", "Cleanup Orphan Favorites"),
                    ("JRP", "Reap Expired Missing Comics And Folders"),
                    ("JRS", "Cleanup Old Sessions"),
                    ("JRV", "Cleanup Orphan Covers"),
                    ("JSR", "Rebuild Full Text Search Virtual Table"),
                    ("JTG", "Cleanup Stale Online Tagging State"),
                    ("OTG", "Look Up Online Tags"),
                    ("OTP", "Await Prompts Pending"),
                    ("RCR", "Restart Codex Server"),
                    ("RCS", "Stop Codex Server"),
                    ("SIO", "Optimize Search Virtual Table"),
                    ("SIR", "Clean Orphan Search Entries"),
                    ("SIX", "Clear Full Text Search Table"),
                    ("SSC", "Sync New Search Entries"),
                    ("SSU", "Sync Old Search Entries"),
                    ("TWR", "Write Comic Tags"),
                    ("WPO", "Poll Library"),
                    ("WRS", "Restart File Watcher"),
                ],
                db_index=True,
                max_length=3,
            ),
        ),
    ]
