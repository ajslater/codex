"""
Browser table view + per-user favorites.

Bundles every settings / model schema change from the table-view and
favorites release tracks into one migration so a fresh install only
runs ``0042`` once instead of four chained migrations.

* ``SettingsBrowser`` gains the table-view columns —
  ``view_mode`` / ``table_columns`` / ``table_cover_size`` plus
  ``order_extra_keys`` for the multi-column-sort tiebreakers — and
  refreshes ``order_by``'s choice list to the post-table-view set
  including the new ``favorite`` sort key.

* The post-table-view ``order_by`` set drops the original
  ``issue_number`` / ``issue_suffix`` pair in favor of a single
  compound ``issue`` entry, and adds ~30 keys: per-relation FK names
  (publisher / imprint / series / volume / scan_info / tagger /
  main_character / main_team / original_format), M2M keys
  (characters, genres, locations, series_groups, stories, tags,
  teams, credits, identifiers, story_arcs, universes), the small
  remaining grab-bag (country, language, reading_direction,
  age_rating, file_type, monochrome, metadata_mtime), and the new
  ``favorite`` from the favorites work. Stored settings carrying the
  retired ``issue_number`` / ``issue_suffix`` keys 400 until re-saved.

* ``Favorite`` is a new per-user table keyed by
  ``(user, group, target_id)`` where ``group`` is the same
  single-letter code already used in browser URLs. The composite
  unique constraint doubles as the lookup index for both the
  "favorites only" filter and the per-row annotation in table view.

* ``SettingsBrowserFilters.favorite`` is a plain boolean toggle —
  "favorites only" — that the browser filter pipeline reads
  alongside ``bookmark``. Default ``False`` means existing rows opt
  in to "show everything" without backfill.

* ``LibrarianStatus.status_type`` choice list grows by one entry —
  ``JRF`` Cleanup Orphan Favorites — for the nightly orphan-favorite
  sweep that backstops the post-delete signals.

``table_cover_size`` ships with only the ``sm`` choice — the original
``xs`` option was dropped before the feature shipped, but the field
stays around so a future medium / large can be added without a fresh
migration.

These are mostly pure choice-metadata edits on existing CharField
columns plus four ``AddField``s and one ``CreateModel``; Django emits
``ALTER TABLE`` only for the new columns and the new
``codex_favorite`` table.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

_ORDER_BY_CHOICES = [
    ("created_at", "Added Time"),
    ("age_rating", "Age Rating"),
    ("characters", "Characters"),
    ("child_count", "Child Count"),
    ("country", "Country"),
    ("credits", "Credits"),
    ("critical_rating", "Critical Rating"),
    ("day", "Day"),
    ("favorite", "Favorite"),
    ("filename", "Filename"),
    ("size", "File Size"),
    ("file_type", "File Type"),
    ("original_format", "Format"),
    ("genres", "Genres"),
    ("identifiers", "Identifiers"),
    ("imprint_name", "Imprint"),
    ("issue", "Issue"),
    ("language", "Language"),
    ("bookmark_updated_at", "Last Read"),
    ("locations", "Locations"),
    ("main_character", "Main Character"),
    ("main_team", "Main Team"),
    ("metadata_mtime", "Metadata Updated"),
    ("month", "Month"),
    ("monochrome", "Monochrome"),
    ("sort_name", "Name"),
    ("page_count", "Page Count"),
    ("publisher_name", "Publisher"),
    ("date", "Publish Date"),
    ("reading_direction", "Reading Direction"),
    ("scan_info", "Scan Info"),
    ("search_score", "Search Score"),
    ("series_name", "Series"),
    ("series_groups", "Series Groups"),
    ("stories", "Stories"),
    ("story_arc_number", "Story Arc Number"),
    ("story_arcs", "Story Arcs"),
    ("tags", "Tags"),
    ("tagger", "Tagger"),
    ("teams", "Teams"),
    ("universes", "Universes"),
    ("updated_at", "Updated Time"),
    ("volume_name", "Volume"),
    ("year", "Year"),
]

_FAVORITE_GROUP_CHOICES = [
    ("p", "Publisher"),
    ("i", "Imprint"),
    ("s", "Series"),
    ("v", "Volume"),
    ("f", "Folder"),
    ("a", "Story Arc"),
    ("c", "Comic"),
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
    ("JID", "Check Integrity Of Entire Database"),
    ("JIF", "Check Integrtity Of Database Foreign Keys"),
    ("JIS", "Check Integrity Of Full Text Virtual Table"),
    ("JLV", "Check Codex Latest Version"),
    ("JRB", "Cleanup Orphan Bookmarks"),
    ("JRF", "Cleanup Orphan Favorites"),
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


class Migration(migrations.Migration):
    """Add table-view fields, the Favorite model, and the favorites filter."""

    dependencies = [
        ("codex", "0041_cleanup_phantom_comic_as_folder_rows"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Table-view columns on SettingsBrowser.
        migrations.AddField(
            model_name="settingsbrowser",
            name="table_columns",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="settingsbrowser",
            name="table_cover_size",
            field=models.CharField(
                choices=[("sm", "Small")],
                default="sm",
                max_length=4,
            ),
        ),
        migrations.AddField(
            model_name="settingsbrowser",
            name="view_mode",
            field=models.CharField(
                choices=[("cover", "Cover"), ("table", "Table")],
                default="cover",
                max_length=8,
            ),
        ),
        # Multi-column-sort tiebreakers.
        migrations.AddField(
            model_name="settingsbrowser",
            name="order_extra_keys",
            field=models.JSONField(default=list),
        ),
        # Refresh order_by choices to the post-table-view + favorite set.
        migrations.AlterField(
            model_name="settingsbrowser",
            name="order_by",
            field=models.CharField(
                choices=_ORDER_BY_CHOICES,
                default="",
                max_length=32,
            ),
        ),
        # Favorite model — per-user (user, group, target_id) tag.
        migrations.CreateModel(
            name="Favorite",
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
                    "group",
                    models.CharField(
                        choices=_FAVORITE_GROUP_CHOICES,
                        max_length=1,
                    ),
                ),
                ("target_id", models.PositiveIntegerField()),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "get_latest_by": "updated_at",
                "abstract": False,
                "unique_together": {("user", "group", "target_id")},
            },
        ),
        # "Favorites only" boolean filter on the browser settings row.
        migrations.AddField(
            model_name="settingsbrowserfilters",
            name="favorite",
            field=models.BooleanField(default=False),
        ),
        # Register the JRF Cleanup Orphan Favorites status code.
        migrations.AlterField(
            model_name="librarianstatus",
            name="status_type",
            field=models.CharField(
                choices=_LIBRARIAN_STATUS_CHOICES,
                db_index=True,
                max_length=3,
            ),
        ),
    ]
