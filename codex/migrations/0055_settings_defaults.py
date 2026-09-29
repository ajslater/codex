"""
Site default browser and reader settings, as one admin singleton.

- **``SettingsDefaults``** holds the settings new sessions are seeded with and
  resets restore. One row, pk=1.
- **The Default View (``BG``) admin flag folds into
  ``SettingsDefaults.top_collection``.** The stored value is the one new
  sessions actually landed on, not the raw flag: an off flag, imprints or
  volumes (hidden by the default show flags), folders with Folder View off,
  and anything unrecognized all landed on publishers. The flag row is then
  deleted, and ``AdminFlag.key`` loses the choice.

The reverse recreates the flag, on, holding the stored top collection.
"""

from django.db import migrations, models

_BG_KEY = "BG"
_FV_KEY = "FV"
_FALLBACK_TOP_COLLECTION = "publishers"
# Top collections a new session could land on whatever the default show
# flags said. Folders also needed Folder View.
_REACHABLE_TOP_COLLECTIONS = frozenset({"publishers", "series", "comics", "arcs"})


def _effective_top_collection(bg, fv) -> str:
    """Map the Default View flag onto the top collection it produced."""
    if bg is None or not bg.on:
        return _FALLBACK_TOP_COLLECTION
    if bg.value in _REACHABLE_TOP_COLLECTIONS:
        return bg.value
    if bg.value == "folders" and fv is not None and fv.on:
        return bg.value
    return _FALLBACK_TOP_COLLECTION


def seed_settings_defaults(apps, _schema_editor) -> None:
    """Create the singleton from the Default View flag, then drop the flag."""
    admin_flag_model = apps.get_model("codex", "AdminFlag")
    settings_defaults_model = apps.get_model("codex", "SettingsDefaults")
    flags = {
        flag.key: flag
        for flag in admin_flag_model.objects.filter(key__in=(_BG_KEY, _FV_KEY))
    }
    bg = flags.get(_BG_KEY)
    top_collection = _effective_top_collection(bg, flags.get(_FV_KEY))
    settings_defaults_model.objects.update_or_create(
        pk=1,
        defaults={
            "top_collection": top_collection,
            "bookmark": "",
            "table_columns": {},
        },
    )
    if bg is None:
        return
    mapping = f"on={bg.on}, value={bg.value!r}"
    print(f"\nDefault View flag ({mapping}) became top collection {top_collection!r}.")
    admin_flag_model.objects.filter(key=_BG_KEY).delete()


def unseed_settings_defaults(apps, _schema_editor) -> None:
    """Recreate the Default View flag from the singleton."""
    admin_flag_model = apps.get_model("codex", "AdminFlag")
    settings_defaults_model = apps.get_model("codex", "SettingsDefaults")
    row = settings_defaults_model.objects.filter(pk=1).first()
    value = row.top_collection if row else _FALLBACK_TOP_COLLECTION
    admin_flag_model.objects.update_or_create(
        key=_BG_KEY, defaults={"on": True, "value": value}
    )
    settings_defaults_model.objects.all().delete()


class Migration(migrations.Migration):
    """SettingsDefaults singleton; the BG flag folds into it."""

    dependencies = [
        ("codex", "0054_post_v2_3_3_schema"),
    ]

    operations = [
        migrations.CreateModel(
            name="SettingsDefaults",
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
                    "top_collection",
                    models.CharField(
                        choices=[
                            ("publishers", "Publishers"),
                            ("imprints", "Imprints"),
                            ("series", "Series"),
                            ("volumes", "Volumes"),
                            ("comics", "Issues"),
                            ("folders", "Folders"),
                            ("arcs", "Story Arcs"),
                        ],
                        default="publishers",
                        max_length=32,
                    ),
                ),
                ("show_publishers", models.BooleanField(default=True)),
                ("show_imprints", models.BooleanField(default=False)),
                ("show_series", models.BooleanField(default=True)),
                ("show_volumes", models.BooleanField(default=False)),
                (
                    "order_by",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "Automatic"),
                            ("created_at", "Added Time"),
                            ("age_rating", "Age Rating"),
                            ("characters", "Characters"),
                            ("child_count", "Child Count"),
                            ("community_rating", "Community Rating"),
                            ("country", "Country"),
                            ("credits", "Credits"),
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
                            ("metadata_mtime", "Tags Updated"),
                            ("month", "Month"),
                            ("monochrome", "Monochrome"),
                            ("sort_name", "Name"),
                            ("page_count", "Page Count"),
                            ("publisher_name", "Publisher"),
                            ("date", "Publish Date"),
                            ("reading_direction", "Reading Direction"),
                            ("reprints", "Reprints"),
                            ("scan_info", "Scan Info"),
                            ("series_name", "Series"),
                            ("series_groups", "Series Groups"),
                            ("stories", "Stories"),
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
                ("order_reverse", models.BooleanField(default=False)),
                (
                    "view_mode",
                    models.CharField(
                        choices=[("cover", "Cover"), ("table", "Table")],
                        default="cover",
                        max_length=8,
                    ),
                ),
                ("twenty_four_hour_time", models.BooleanField(default=False)),
                ("always_show_filename", models.BooleanField(default=False)),
                (
                    "bookmark",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "All"),
                            ("IN_PROGRESS", "In Progress"),
                            ("READ", "Read"),
                            ("UNREAD", "Unread"),
                        ],
                        default="",
                        max_length=16,
                    ),
                ),
                ("table_columns", models.JSONField(default=dict)),
                (
                    "fit_to",
                    models.CharField(
                        choices=[
                            ("S", "Screen"),
                            ("W", "Width"),
                            ("H", "Height"),
                            ("O", "Orig"),
                        ],
                        default="W",
                        max_length=1,
                    ),
                ),
                (
                    "reading_direction",
                    models.CharField(
                        choices=[
                            ("rtl", "Rtl"),
                            ("ltr", "Ltr"),
                            ("ttb", "Ttb"),
                            ("btt", "Btt"),
                        ],
                        default="ltr",
                        max_length=3,
                    ),
                ),
                ("two_pages", models.BooleanField(default=False)),
                ("page_transition", models.BooleanField(default=True)),
                ("cache_book", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name_plural": "SettingsDefaults",
                "get_latest_by": "updated_at",
                "abstract": False,
            },
        ),
        migrations.RunPython(seed_settings_defaults, unseed_settings_defaults),
        migrations.AlterField(
            model_name="adminflag",
            name="key",
            field=models.CharField(
                choices=[
                    ("AA", "Anonymous User Age Rating"),
                    ("AK", "Api Key"),
                    ("AR", "Age Rating Default"),
                    ("AU", "Auto Update"),
                    ("BT", "Banner Text"),
                    ("CM", "Custom Cover Max Upload Mb"),
                    ("FV", "Folder View"),
                    ("IM", "Import Metadata"),
                    ("LI", "Lazy Import Metadata"),
                    ("MP", "Browser Max Obj Per Page"),
                    ("NU", "Non Users"),
                    ("RG", "Registration"),
                    ("RV", "Register Verification"),
                    ("ST", "Send Telemetry"),
                ],
                db_index=True,
                max_length=2,
            ),
        ),
    ]
