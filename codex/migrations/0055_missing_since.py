"""
Keep a vanished path's row instead of deleting it immediately.

A scan that cannot find a file infers a deletion, and the delete cascades
the comic's bookmarks away with it. The reporter lost a whole publisher's
read progress twice to a share that was unreachable for 41-50 minutes --
far longer than the five-second second look can cover.

``missing_since`` records when a scan last failed to find the path. NULL
means present, which is the correct initial state for every existing row,
so there is no backfill. Nothing reads or writes the column yet; this
migration only makes the state expressible.

Four concrete tables inherit the field from ``WatchedPath``. It is inert
on ``FailedImport`` and ``CustomCover``: the poller walks only Folder,
Comic and FailedImport, ``Snapshot.is_cover`` is hardcoded False, and a
custom cover is created by upload with ``library=None`` so it can never
match the poller's ``library__path`` filter. The field stays on the base
anyway -- adding a NULL column is metadata-only, and one declaration
keeps the inheritance auditable.

Only Comic and Folder get an index, and it is partial. The per-request
visibility filter is ``missing_since IS NULL``, which matches ~every row;
no index can serve that and SQLite correctly declines to try. The nightly
reap is ``missing_since < cutoff``, which matches ~no rows. A partial
index over the non-NULL rows serves the reap for a handful of entries and
costs nothing on insert, and SQLite's implication prover recognises that
``missing_since < ?`` implies ``missing_since IS NOT NULL``, so the reap
needs no redundant conjunct. The precedent is LibrarianStatus's partial
index on its two nullable datetime markers.

Fields land before indexes, and ``Migration.atomic`` is on by default
while SQLite rolls DDL back, so this is all-or-nothing.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add missing_since and its two partial indexes."""

    dependencies = [
        ("codex", "0054_bookmark_partial_unique"),
    ]

    operations = [
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
    ]
