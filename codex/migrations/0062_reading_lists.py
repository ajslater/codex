"""
Reading lists behind the ``arcs`` collection.

The browser's ``arcs`` collection reads reading lists instead of the
story-arc tag tables, which stay the importer's. In order:

1. Create the reading-list tables.
2. Relabel the collection "Reading Lists" in the choice fields.
3. Build one global list per story-arc sort name, the grouping arc browse
   used, with a ``tags`` source and one entry per tagged comic in arc
   order: arc number, then date, then pk, NULLs first as SQLite sorts
   them. Each source's revision is left blank, so the importer's first
   tag sync rebuilds the list and fills in every entry's reference.
4. Point what held a story-arc pk as a browse collection at the list
   instead: shelf items, saved routes and reader settings. Rows that
   collapse onto one list keep the newest.
5. ``SettingsReader.story_arc`` becomes ``reading_list``.

Self-contained on purpose: it reads historical models only, so later
changes to the tag sync cannot change what it did.
"""

import uuid
from collections import defaultdict

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import codex.models.fields

_ARCS = "arcs"
_TAGS = "tags"
_STORY = "story"
_BATCH = 1000


def _arc_groups(story_arc_model) -> dict:
    """Group arcs by sort name: first name and cover, every pk."""
    groups: dict = {}
    rows = story_arc_model.objects.order_by("pk").values_list(
        "pk", "name", "sort_name", "custom_cover_id"
    )
    for pk, name, sort_name, cover_id in rows:
        group = groups.setdefault(
            sort_name, {"name": name, "arc_pks": [], "cover_id": None}
        )
        group["arc_pks"].append(pk)
        if group["cover_id"] is None:
            group["cover_id"] = cover_id
    return groups


def _issue(number, suffix) -> str:
    """Render an issue for display, as ``10``, ``1.5`` or ``2a``."""
    text = "" if number is None else format(number.normalize(), "f")
    return f"{text}{suffix or ''}"


def _lower(number, known) -> bool:
    """Whether ``number`` beats ``known``: MIN() ignores NULLs, as arc browse did."""
    return number is not None and (known is None or number < known)


def _members(comic_model) -> dict:
    """Map each arc sort name to its comics, with each comic's lowest number."""
    through = comic_model.story_arc_numbers.through
    rows = through.objects.values_list(
        "storyarcnumber__story_arc__sort_name",
        "comic_id",
        "storyarcnumber__number",
        "comic__date",
        "comic__series__name",
        "comic__issue_number",
        "comic__issue_suffix",
        "comic__year",
    )
    members: dict = defaultdict(dict)
    for sort_name, comic_pk, number, date, series, issue, suffix, year in rows:
        comics = members[sort_name]
        known = comics.get(comic_pk)
        if known is not None and not _lower(number, known["number"]):
            continue
        comics[comic_pk] = {
            "number": number,
            "date": date,
            "series": series or "",
            "issue": _issue(issue, suffix),
            "year": year,
        }
    return members


def _sort_key(item):
    """Arc number, then date, then pk, NULLs first."""
    pk, info = item
    number, date = info["number"], info["date"]
    return (number is not None, number or 0, date is not None, date or "", pk)


def _build_lists(apps) -> dict:
    """Create the lists, their tags sources and entries; map arc pk to list pk."""
    story_arc_model = apps.get_model("codex", "StoryArc")
    comic_model = apps.get_model("codex", "Comic")
    reading_list_model = apps.get_model("codex", "ReadingList")
    source_model = apps.get_model("codex", "ReadingListSource")
    entry_model = apps.get_model("codex", "ReadingListEntry")

    groups = _arc_groups(story_arc_model)
    if not groups:
        return {}
    reading_list_model.objects.bulk_create(
        (
            reading_list_model(
                name=group["name"],
                sort_name=sort_name,
                custom_cover_id=group["cover_id"],
                list_type=_STORY,
                uuid=uuid.uuid4(),
            )
            for sort_name, group in groups.items()
        ),
        batch_size=_BATCH,
    )
    list_pks = dict(
        reading_list_model.objects.filter(user__isnull=True).values_list(
            "sort_name", "pk"
        )
    )
    members = _members(comic_model)
    sources = []
    entries = []
    for sort_name, list_pk in list_pks.items():
        comics = sorted(members.get(sort_name, {}).items(), key=_sort_key)
        numbers = [info["number"] for _, info in comics]
        ordered = None not in numbers and len(set(numbers)) == len(numbers)
        sources.append(
            source_model(
                reading_list_id=list_pk,
                kind=_TAGS,
                ref=sort_name,
                revision="",
                rank=0,
                ordered=ordered,
            )
        )
        entries.extend(
            entry_model(
                reading_list_id=list_pk,
                position=position,
                comic_id=comic_pk,
                series_name=info["series"],
                issue=info["issue"],
                year=info["year"],
                match_tier="tagged",
            )
            for position, (comic_pk, info) in enumerate(comics)
        )
    source_model.objects.bulk_create(sources, batch_size=_BATCH)
    entry_model.objects.bulk_create(entries, batch_size=_BATCH)
    return {
        arc_pk: list_pks[sort_name]
        for sort_name, group in groups.items()
        for arc_pk in group["arc_pks"]
    }


def _remap_shelf_items(apps, arc_to_list: dict) -> None:
    """Shelve the list where the arc was; drop items that collapse onto one."""
    shelf_item_model = apps.get_model("codex", "ShelfItem")
    items = shelf_item_model.objects.filter(collection=_ARCS)
    seen = set()
    remapped = []
    for shelf_id, target_id in items.order_by("pk").values_list(
        "shelf_id", "target_id"
    ):
        target = arc_to_list.get(target_id)
        if target is None or (shelf_id, target) in seen:
            continue
        seen.add((shelf_id, target))
        remapped.append(
            shelf_item_model(shelf_id=shelf_id, collection=_ARCS, target_id=target)
        )
    # Replace rather than update: an old arc pk can equal a new list pk, so
    # updating in place could meet the unique (shelf, collection, target).
    items.delete()
    shelf_item_model.objects.bulk_create(remapped, batch_size=_BATCH)


def _remap_last_routes(apps, arc_to_list: dict) -> None:
    """Point saved routes into an arc at its list."""
    last_route_model = apps.get_model("codex", "SettingsBrowserLastRoute")
    update = []
    for route in last_route_model.objects.filter(collection=_ARCS):
        pks = list(
            dict.fromkeys(
                arc_to_list[pk] for pk in route.pks or () if pk in arc_to_list
            )
        )
        if pks != route.pks:
            route.pks = pks
            update.append(route)
    last_route_model.objects.bulk_update(update, ("pks",), batch_size=_BATCH)


def _remap_reader_settings(apps, arc_to_list: dict) -> None:
    """Arc-scoped reader settings scope to the list; the newest row wins."""
    settings_reader_model = apps.get_model("codex", "SettingsReader")
    seen = set()
    update, delete = [], []
    rows = settings_reader_model.objects.filter(story_arc__isnull=False).order_by(
        "-updated_at", "-pk"
    )
    for row in rows:
        target = arc_to_list.get(row.story_arc_id)
        key = (row.user_id, row.session_id, row.client, target)
        if target is None or key in seen:
            delete.append(row.pk)
            continue
        seen.add(key)
        row.reading_list_id = target
        update.append(row)
    settings_reader_model.objects.filter(pk__in=delete).delete()
    settings_reader_model.objects.bulk_update(
        update, ("reading_list",), batch_size=_BATCH
    )


def _move_arcs_to_reading_lists(apps, _schema_editor) -> None:
    """Build the lists and repoint everything that named an arc pk."""
    arc_to_list = _build_lists(apps)
    _remap_shelf_items(apps, arc_to_list)
    _remap_last_routes(apps, arc_to_list)
    _remap_reader_settings(apps, arc_to_list)


def _list_to_arc(apps) -> dict:
    """Map each list from tags back to the first arc of its sort name."""
    story_arc_model = apps.get_model("codex", "StoryArc")
    source_model = apps.get_model("codex", "ReadingListSource")
    first_arc: dict = {}
    for pk, sort_name in story_arc_model.objects.order_by("pk").values_list(
        "pk", "sort_name"
    ):
        first_arc.setdefault(sort_name, pk)
    return {
        list_pk: first_arc[ref]
        for list_pk, ref in source_model.objects.filter(kind=_TAGS).values_list(
            "reading_list_id", "ref"
        )
        if ref in first_arc
    }


def _move_reading_lists_to_arcs(apps, _schema_editor) -> None:
    """
    Point shelf items, saved routes and reader settings back at arcs.

    Only lists from tags have an arc to go back to. Rows for any other list
    are dropped: a reader setting left with no scope would read as a second
    global row and break its unique constraint.
    """
    list_to_arc = _list_to_arc(apps)
    _remap_shelf_items(apps, list_to_arc)
    _remap_last_routes(apps, list_to_arc)
    settings_reader_model = apps.get_model("codex", "SettingsReader")
    rows = settings_reader_model.objects.filter(reading_list__isnull=False)
    update, delete = [], []
    for row in rows:
        arc_pk = list_to_arc.get(row.reading_list_id)
        if arc_pk is None:
            delete.append(row.pk)
            continue
        row.story_arc_id = arc_pk
        update.append(row)
    settings_reader_model.objects.filter(pk__in=delete).delete()
    settings_reader_model.objects.bulk_update(update, ("story_arc",), batch_size=_BATCH)


class Migration(migrations.Migration):
    """Move the arcs collection onto reading lists."""

    dependencies = [
        ("codex", "0061_tagging_keep_formats"),
        ("sessions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReadingList",
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
                        db_index=True, default="", max_length=128
                    ),
                ),
                (
                    "sort_name",
                    codex.models.fields.CleaningCharField(
                        db_collation="nocase", db_index=True, default="", max_length=128
                    ),
                ),
                (
                    "uuid",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "description",
                    codex.models.fields.CleaningTextField(blank=True, default=""),
                ),
                (
                    "list_notes",
                    codex.models.fields.CleaningTextField(blank=True, default=""),
                ),
                (
                    "list_type",
                    codex.models.fields.CleaningCharField(
                        blank=True, default="", max_length=64
                    ),
                ),
                (
                    "start_year",
                    models.PositiveSmallIntegerField(default=None, null=True),
                ),
                ("end_year", models.PositiveSmallIntegerField(default=None, null=True)),
                ("edited_fields", models.JSONField(default=list)),
                ("order_locked", models.BooleanField(default=False)),
                ("extra", models.JSONField(default=dict)),
            ],
            options={
                "get_latest_by": "updated_at",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ReadingListEntry",
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
                ("position", models.PositiveIntegerField(default=0)),
                ("reference", models.JSONField(default=dict)),
                (
                    "series_name",
                    codex.models.fields.CleaningCharField(
                        blank=True, default="", max_length=128
                    ),
                ),
                ("issue", models.CharField(blank=True, default="", max_length=32)),
                ("year", models.PositiveSmallIntegerField(default=None, null=True)),
                (
                    "match_tier",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "Missing"),
                            ("manual", "By hand"),
                            ("tagged", "Tagged"),
                            ("mapping", "Series mapping"),
                            ("issue_id", "Issue id"),
                            ("series_id", "Series id"),
                            ("exact_name", "Exact name"),
                            ("normalized_name", "Normalized name"),
                        ],
                        default="",
                        max_length=15,
                    ),
                ),
                ("needs_review", models.BooleanField(db_index=True, default=False)),
                ("ignored", models.BooleanField(default=False)),
                ("manual", models.BooleanField(default=False)),
                ("entry_type", models.CharField(blank=True, default="", max_length=32)),
                ("source_ids", models.JSONField(default=list)),
            ],
            options={
                "verbose_name_plural": "reading list entries",
                "get_latest_by": "updated_at",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ReadingListSeriesMapping",
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
                ("series_key", models.CharField(db_index=True, max_length=128)),
                ("year", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "get_latest_by": "updated_at",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ReadingListSource",
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
                    "kind",
                    models.CharField(
                        choices=[
                            ("tags", "File Tags"),
                            ("upload", "Upload"),
                            ("url", "URL"),
                            ("catalog", "DieselTech Catalog"),
                            ("metron_list", "Metron Reading List"),
                            ("metron_arc", "Metron Story Arc"),
                            ("comicvine_arc", "Comic Vine Story Arc"),
                        ],
                        db_index=True,
                        max_length=13,
                    ),
                ),
                ("ref", models.CharField(db_index=True, max_length=1024)),
                ("revision", models.CharField(blank=True, default="", max_length=128)),
                (
                    "attribution_source",
                    codex.models.fields.CleaningCharField(
                        blank=True, default="", max_length=128
                    ),
                ),
                (
                    "attribution_url",
                    models.CharField(blank=True, default="", max_length=1024),
                ),
                ("rank", models.PositiveSmallIntegerField(default=0)),
                ("ordered", models.BooleanField(default=True)),
                ("document", models.JSONField(default=None, null=True)),
                ("fetched_at", models.DateTimeField(default=None, null=True)),
            ],
            options={
                "get_latest_by": "updated_at",
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="readinglist",
            name="custom_cover",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                to="codex.customcover",
            ),
        ),
        migrations.AddField(
            model_name="readinglist",
            name="user",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="readinglistentry",
            name="comic",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reading_list_entries",
                to="codex.comic",
            ),
        ),
        migrations.AddField(
            model_name="readinglistentry",
            name="reading_list",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="entries",
                to="codex.readinglist",
            ),
        ),
        migrations.AddField(
            model_name="readinglistseriesmapping",
            name="series",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="codex.series",
            ),
        ),
        migrations.AddField(
            model_name="readinglistsource",
            name="reading_list",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sources",
                to="codex.readinglist",
            ),
        ),
        migrations.AddConstraint(
            model_name="readinglist",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", False)),
                fields=("user", "name"),
                name="unique_readinglist_user_name",
            ),
        ),
        migrations.AddIndex(
            model_name="readinglistentry",
            index=models.Index(
                fields=["reading_list", "position"], name="readinglistentry_list_pos"
            ),
        ),
        migrations.AddIndex(
            model_name="readinglistentry",
            index=models.Index(
                fields=["comic", "reading_list"], name="readinglistentry_comic_list"
            ),
        ),
        migrations.AddConstraint(
            model_name="readinglistseriesmapping",
            constraint=models.UniqueConstraint(
                fields=("series_key", "year"),
                name="unique_readinglistseriesmapping_key_year",
            ),
        ),
        migrations.AddIndex(
            model_name="readinglistsource",
            index=models.Index(
                fields=["kind", "ref"], name="readinglistsource_kind_ref"
            ),
        ),
        migrations.AddConstraint(
            model_name="readinglistsource",
            constraint=models.UniqueConstraint(
                fields=("reading_list", "kind", "ref"),
                name="unique_readinglistsource_list_kind_ref",
            ),
        ),
        migrations.AlterField(
            model_name="settingsbrowser",
            name="order_by",
            field=models.CharField(
                choices=[
                    ("created_at", "Added Time"),
                    ("age_rating", "Age Rating"),
                    ("characters", "Characters"),
                    ("child_count", "Child Count"),
                    ("community_rating", "Community Rating"),
                    ("country", "Country"),
                    ("credits", "Credits"),
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
                    ("search_score", "Search Score"),
                    ("series_name", "Series"),
                    ("series_groups", "Series Groups"),
                    ("shelved", "Shelved"),
                    ("stories", "Stories"),
                    ("story_arc_number", "Reading Order"),
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
        migrations.AlterField(
            model_name="settingsbrowser",
            name="top_collection",
            field=models.CharField(
                choices=[
                    ("publishers", "Publishers"),
                    ("imprints", "Imprints"),
                    ("series", "Series"),
                    ("volumes", "Volumes"),
                    ("comics", "Issues"),
                    ("folders", "Folders"),
                    ("arcs", "Reading Lists"),
                ],
                default="publishers",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="settingsbrowserlastroute",
            name="collection",
            field=models.CharField(
                choices=[
                    ("publishers", "Publishers"),
                    ("imprints", "Imprints"),
                    ("series", "Series"),
                    ("volumes", "Volumes"),
                    ("comics", "Issues"),
                    ("folders", "Folders"),
                    ("arcs", "Reading Lists"),
                    ("root", "Root"),
                ],
                default="root",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="settingsdefaults",
            name="top_collection",
            field=models.CharField(
                choices=[
                    ("publishers", "Publishers"),
                    ("imprints", "Imprints"),
                    ("series", "Series"),
                    ("volumes", "Volumes"),
                    ("comics", "Issues"),
                    ("folders", "Folders"),
                    ("arcs", "Reading Lists"),
                ],
                default="publishers",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="shelfitem",
            name="collection",
            field=models.CharField(
                choices=[
                    ("publishers", "Publishers"),
                    ("imprints", "Imprints"),
                    ("series", "Series"),
                    ("volumes", "Volumes"),
                    ("folders", "Folders"),
                    ("arcs", "Reading Lists"),
                    ("comics", "Issues"),
                ],
                max_length=16,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="settingsreader",
            name="settingsreader_scope_xor",
        ),
        migrations.RemoveConstraint(
            model_name="settingsreader",
            name="unique_settingsreader_user_global",
        ),
        migrations.RemoveConstraint(
            model_name="settingsreader",
            name="unique_settingsreader_session_global",
        ),
        migrations.RemoveConstraint(
            model_name="settingsreader",
            name="unique_settingsreader_user_story_arc",
        ),
        migrations.RemoveConstraint(
            model_name="settingsreader",
            name="unique_settingsreader_session_story_arc",
        ),
        migrations.AddField(
            model_name="settingsreader",
            name="reading_list",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="codex.readinglist",
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
                    ("JKH", "Hash Comics For Koreader Sync"),
                    ("JLV", "Check Codex Latest Version"),
                    ("JRB", "Cleanup Orphan Bookmarks"),
                    ("JRF", "Cleanup Orphan Shelf Items"),
                    ("JRP", "Reap Expired Missing Comics And Folders"),
                    ("JRS", "Cleanup Old Sessions"),
                    ("JRV", "Cleanup Orphan Covers"),
                    ("JSR", "Rebuild Full Text Search Virtual Table"),
                    ("JTG", "Cleanup Stale Online Tagging State"),
                    ("OTG", "Look Up Online Tags"),
                    ("OTP", "Await Prompts Pending"),
                    ("RCR", "Restart Codex Server"),
                    ("RCS", "Stop Codex Server"),
                    ("RLF", "Fetch Reading Lists"),
                    ("RLI", "Import Reading Lists"),
                    ("RLM", "Match Reading List Issues"),
                    ("RLS", "Sync Reading Lists From Tags"),
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
        migrations.AddField(
            model_name="settingsbrowserfilters",
            name="reading_list_kind",
            field=models.CharField(
                blank=True,
                choices=[("", "All"), ("curated", "Curated"), ("tags", "From Tags")],
                default="",
                max_length=16,
            ),
        ),
        migrations.RunPython(_move_arcs_to_reading_lists, _move_reading_lists_to_arcs),
        migrations.RemoveField(
            model_name="settingsreader",
            name="story_arc",
        ),
        migrations.AddConstraint(
            model_name="settingsreader",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("comic__isnull", True),
                        ("folder__isnull", True),
                        ("reading_list__isnull", True),
                        ("series__isnull", True),
                    ),
                    models.Q(
                        ("comic__isnull", False),
                        ("folder__isnull", True),
                        ("reading_list__isnull", True),
                        ("series__isnull", True),
                    ),
                    models.Q(
                        ("comic__isnull", True),
                        ("folder__isnull", True),
                        ("reading_list__isnull", True),
                        ("series__isnull", False),
                    ),
                    models.Q(
                        ("comic__isnull", True),
                        ("folder__isnull", False),
                        ("reading_list__isnull", True),
                        ("series__isnull", True),
                    ),
                    models.Q(
                        ("comic__isnull", True),
                        ("folder__isnull", True),
                        ("reading_list__isnull", False),
                        ("series__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="settingsreader_scope_xor",
            ),
        ),
        migrations.AddConstraint(
            model_name="settingsreader",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("user__isnull", False),
                    ("comic__isnull", True),
                    ("folder__isnull", True),
                    ("reading_list__isnull", True),
                    ("series__isnull", True),
                ),
                fields=("user", "client"),
                name="unique_settingsreader_user_global",
            ),
        ),
        migrations.AddConstraint(
            model_name="settingsreader",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("session__isnull", False),
                    ("comic__isnull", True),
                    ("folder__isnull", True),
                    ("reading_list__isnull", True),
                    ("series__isnull", True),
                ),
                fields=("session", "client"),
                name="unique_settingsreader_session_global",
            ),
        ),
        migrations.AddConstraint(
            model_name="settingsreader",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("reading_list__isnull", False), ("user__isnull", False)
                ),
                fields=("user", "client", "reading_list"),
                name="unique_settingsreader_user_reading_list",
            ),
        ),
        migrations.AddConstraint(
            model_name="settingsreader",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("reading_list__isnull", False), ("session__isnull", False)
                ),
                fields=("session", "client", "reading_list"),
                name="unique_settingsreader_session_reading_list",
            ),
        ),
    ]
