"""Phase 7 M2M-sort experiment: register 11 M2M keys in the order_by enum."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Expand ``order_by`` choices with the M2M sort keys."""

    dependencies = [
        ("codex", "0042_browser_table_view_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="settingsbrowser",
            name="order_by",
            field=models.CharField(
                choices=[
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
                    ("issue_number", "Issue Number"),
                    ("issue_suffix", "Issue Suffix"),
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
                ],
                default="",
                max_length=32,
            ),
        ),
    ]
