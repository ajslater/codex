"""
Update choice metadata for ``SettingsBrowser`` table-view fields.

- ``order_by`` gains the 20 new keys from Phase 1 / Step 4
  (series_name, volume_name, publisher_name, etc.).
- ``table_cover_size`` drops ``xs``; only ``sm`` (~32px) survives in v1.

Schema-only metadata change — no SQL is emitted by Django for choice
edits on existing CharField columns.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Refresh ``order_by`` and ``table_cover_size`` choices."""

    dependencies = [
        ("codex", "0041_browser_table_view"),
    ]

    operations = [
        migrations.AlterField(
            model_name="settingsbrowser",
            name="order_by",
            field=models.CharField(
                choices=[
                    ("created_at", "Added Time"),
                    ("age_rating", "Age Rating"),
                    ("child_count", "Child Count"),
                    ("country", "Country"),
                    ("critical_rating", "Critical Rating"),
                    ("day", "Day"),
                    ("filename", "Filename"),
                    ("size", "File Size"),
                    ("file_type", "File Type"),
                    ("original_format", "Format"),
                    ("imprint_name", "Imprint"),
                    ("issue_number", "Issue Number"),
                    ("issue_suffix", "Issue Suffix"),
                    ("language", "Language"),
                    ("bookmark_updated_at", "Last Read"),
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
                    ("story_arc_number", "Story Arc Number"),
                    ("tagger", "Tagger"),
                    ("updated_at", "Updated Time"),
                    ("volume_name", "Volume"),
                    ("year", "Year"),
                ],
                default="",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="settingsbrowser",
            name="table_cover_size",
            field=models.CharField(
                choices=[("sm", "Small")],
                default="sm",
                max_length=4,
            ),
        ),
    ]
