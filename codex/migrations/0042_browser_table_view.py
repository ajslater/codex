"""
Browser table view fields on ``SettingsBrowser``.

Adds ``view_mode``, ``table_columns``, and ``table_cover_size`` for
the new table-view rendering, plus ``order_extra_keys`` for the
multi-column-sort tiebreakers, and refreshes ``order_by``'s choice
list to the post-table-view set.

The post-table-view ``order_by`` set drops the original
``issue_number`` / ``issue_suffix`` pair in favor of a single compound
``issue`` entry, and adds ~30 keys: per-relation FK names (publisher
/ imprint / series / volume / scan_info / tagger / main_character /
main_team / original_format), M2M keys (characters, genres,
locations, series_groups, stories, tags, teams, credits, identifiers,
story_arcs, universes), and the small remaining grab-bag (country,
language, reading_direction, age_rating, file_type, monochrome,
metadata_mtime). Stored settings carrying the retired
``issue_number`` / ``issue_suffix`` keys 400 until re-saved.

These are pure choice-metadata edits on existing ``CharField``
columns plus three ``AddField``s; Django emits ``ALTER TABLE`` only
for the new columns.

``table_cover_size`` ships with only the ``sm`` choice — the original
``xs`` option was dropped before the feature shipped, but the field
stays around so a future medium / large can be added without a fresh
migration.
"""

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


class Migration(migrations.Migration):
    """Add table-view fields and refresh ``order_by`` choices on ``SettingsBrowser``."""

    dependencies = [
        ("codex", "0041_cleanup_phantom_comic_as_folder_rows"),
    ]

    operations = [
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
        # Refresh ``order_by`` choices to the post-table-view set.
        migrations.AlterField(
            model_name="settingsbrowser",
            name="order_by",
            field=models.CharField(
                choices=_ORDER_BY_CHOICES,
                default="",
                max_length=32,
            ),
        ),
    ]
