"""
Everything the schema gained after v2.6.0, as one migration.

v2.6.0 shipped through 0059, so nothing here has reached a release. The four
migrations that landed on develop since are folded together: an upgrading
install applies one migration instead of a chain of four.

In order:

- **KOReader sync document hashes.** The hash columns start null. New imports
  fill them in ``presave``; the JKH janitor job backfills existing comics once
  the KOReader Sync flag is turned on.
- **Shelves, with favorites folded in.** ``Shelf`` is a user's named shelf;
  ``ShelfItem`` places one browsable target on it, and is the old
  ``Favorite`` row re-parented from a user onto a shelf. Existing favorites
  move onto an ordinary shelf named "Favorites", created only for users who
  have favorites. ``SettingsBrowserFilters.shelves`` (a list of shelf pks)
  replaces the ``favorite`` boolean, and stored "favorites only" filters are
  rewritten to point at the owner's Favorites shelf. The ``favorite`` sort
  key and table column are renamed ``shelved``.
- **API keys.** ``UserApiKey`` holds named, revocable, scoped keys. Each DRF
  ``authtoken_token`` row becomes a ``universal`` key named "Universal
  Token", so an existing token keeps logging in everywhere until it is
  revoked. A row whose user no longer exists is dropped. Then the table and
  its migration records are dropped: ``rest_framework.authtoken`` is no
  longer installed. The plaintext server-wide Stats API key in the ``AK``
  admin flag is revoked: its row is deleted and nothing replaces it. Admins
  make their own stats keys now. The digest functions are inlined so later
  model changes cannot alter what this migration wrote.
- **Choice lists** for the admin flags (KOReader Sync, OPDS and Stats API in;
  API Key out) and the librarian statuses (JKH in, JRF relabelled Cleanup
  Orphan Shelf Items).

The reverse is lossy by design: only a user's "Favorites" shelf comes back,
as favorites, and neither the token table nor the Stats API key is rebuilt.
"""

import hashlib
from typing import Final

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

FAVORITES_SHELF_NAME: Final = "Favorites"
_OLD_SORT_KEY: Final = "favorite"
_NEW_SORT_KEY: Final = "shelved"
_TOKEN_TABLE: Final = "authtoken_token"  # noqa: S105
_UNIVERSAL: Final = "universal"
_UNIVERSAL_KEY_NAME: Final = "Universal Token"
_API_KEY_FLAG: Final = "AK"
_PREFIX_LENGTH: Final = 4


def _rename_in_extra_keys(entries, old, new):
    """Rename a sort key inside an ``order_extra_keys`` list."""
    if not isinstance(entries, list):
        return entries, False
    changed = False
    renamed = []
    seen = set()
    for entry in entries:
        item = entry
        if isinstance(item, dict) and item.get("key") == old:
            item = {**item, "key": new}
            changed = True
        key = item.get("key") if isinstance(item, dict) else None
        if key is not None and key in seen:
            # Both the old key and its replacement were stored; one column
            # carries one sort, so the first wins.
            changed = True
            continue
        seen.add(key)
        renamed.append(item)
    return renamed, changed


def _rename_in_memory(memory, old, new):
    """Rename a sort key inside a ``collection_order_memory`` map."""
    if not isinstance(memory, dict):
        return memory, False
    changed = False
    for remembered in memory.values():
        if not isinstance(remembered, dict):
            continue
        if remembered.get("order_by") == old:
            remembered["order_by"] = new
            changed = True
        extras, extras_changed = _rename_in_extra_keys(
            remembered.get("order_extra_keys"), old, new
        )
        if extras_changed:
            remembered["order_extra_keys"] = extras
            changed = True
    return memory, changed


def _rename_in_table_columns(table_columns, old, new):
    """Rename a column key inside a ``{top_collection: [columns]}`` map."""
    if not isinstance(table_columns, dict):
        return table_columns, False
    changed = False
    for top_collection, columns in table_columns.items():
        if not isinstance(columns, list) or old not in columns:
            continue
        renamed = []
        for column in columns:
            key = new if column == old else column
            if key not in renamed:
                renamed.append(key)
        table_columns[top_collection] = renamed
        changed = True
    return table_columns, changed


def _rename_sort_key(apps, old, new):
    """Rename a sort / column key everywhere browser settings store one."""
    settings_browser = apps.get_model("codex", "SettingsBrowser")
    settings_browser.objects.filter(order_by=old).update(order_by=new)
    for row in settings_browser.objects.all().iterator():
        fields = []
        extras, changed = _rename_in_extra_keys(row.order_extra_keys, old, new)
        if changed:
            row.order_extra_keys = extras
            fields.append("order_extra_keys")
        memory, changed = _rename_in_memory(row.collection_order_memory, old, new)
        if changed:
            row.collection_order_memory = memory
            fields.append("collection_order_memory")
        columns, changed = _rename_in_table_columns(row.table_columns, old, new)
        if changed:
            row.table_columns = columns
            fields.append("table_columns")
        if fields:
            row.save(update_fields=fields)

    settings_defaults = apps.get_model("codex", "SettingsDefaults")
    settings_defaults.objects.filter(order_by=old).update(order_by=new)
    for row in settings_defaults.objects.all().iterator():
        columns, changed = _rename_in_table_columns(row.table_columns, old, new)
        if changed:
            row.table_columns = columns
            row.save(update_fields=["table_columns"])


def favorites_to_shelves(apps, schema_editor):
    """
    Fold favorites into shelves.

    Every user who has favorites gets one ordinary shelf named
    "Favorites" holding them; users without favorites get nothing. A
    stored "favorites only" filter (live settings, saved views, OPDS)
    becomes a filter on that shelf, and the ``favorite`` sort key and
    table column become ``shelved``.
    """
    favorite = apps.get_model("codex", "Favorite")
    shelf = apps.get_model("codex", "Shelf")
    filters = apps.get_model("codex", "SettingsBrowserFilters")
    user = apps.get_model("auth", "User")

    # SQLite checks foreign keys only when asked, so a favorite can outlive
    # its user. A shelf for one would fail the FK check ``migrate`` ends with.
    user_ids = (
        favorite.objects.filter(user_id__in=user.objects.values("pk"))
        .values_list("user_id", flat=True)
        .distinct()
    )
    shelf.objects.bulk_create(
        [shelf(user_id=user_id, name=FAVORITES_SHELF_NAME) for user_id in user_ids]
    )
    # Set-based copy that keeps each favorite's timestamps. Only the
    # Favorites shelves exist at this point, so the join is one-to-one.
    schema_editor.execute(
        """
        INSERT INTO codex_shelfitem
            (created_at, updated_at, shelf_id, collection, target_id)
        SELECT f.created_at, f.updated_at, s.id, f.collection, f.target_id
        FROM codex_favorite AS f
        JOIN codex_shelf AS s ON s.user_id = f.user_id
        """
    )

    shelf_pk_by_user = dict(shelf.objects.values_list("user_id", "pk"))
    for row in filters.objects.filter(favorite=True).select_related("browser"):
        # A session-owned row, or a user who had the filter on but no
        # favorites, has no shelf to point at: the filter simply clears.
        shelf_pk = shelf_pk_by_user.get(row.browser.user_id)
        if shelf_pk is not None:
            row.shelves = [shelf_pk]
            row.save(update_fields=["shelves"])

    _rename_sort_key(apps, _OLD_SORT_KEY, _NEW_SORT_KEY)


def shelves_to_favorites(apps, schema_editor):
    """
    Reverse: a user's "Favorites" shelf becomes their favorites again.

    Shelves under any other name, and their items, are lost — the old
    schema has nowhere to keep them.
    """
    shelf = apps.get_model("codex", "Shelf")
    filters = apps.get_model("codex", "SettingsBrowserFilters")

    schema_editor.execute(
        """
        INSERT INTO codex_favorite
            (created_at, updated_at, user_id, collection, target_id)
        SELECT i.created_at, i.updated_at, s.user_id, i.collection, i.target_id
        FROM codex_shelfitem AS i
        JOIN codex_shelf AS s ON s.id = i.shelf_id
        WHERE s.name = %s
        """,
        [FAVORITES_SHELF_NAME],
    )

    favorites_shelf_pks = frozenset(
        shelf.objects.filter(name=FAVORITES_SHELF_NAME).values_list("pk", flat=True)
    )
    for row in filters.objects.exclude(shelves=[]):
        if favorites_shelf_pks.intersection(row.shelves):
            row.favorite = True
            row.save(update_fields=["favorite"])

    _rename_sort_key(apps, _NEW_SORT_KEY, _OLD_SORT_KEY)


def _sha256(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _md5(secret: str) -> str:
    return hashlib.md5(secret.encode(), usedforsecurity=False).hexdigest()


def _migrate_tokens(apps, schema_editor) -> None:
    """Copy each DRF token to a universal key, then drop the token table."""
    connection = schema_editor.connection
    if _TOKEN_TABLE not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT key, user_id FROM {_TOKEN_TABLE}")  # noqa: S608
        rows = cursor.fetchall()
    # A token whose user is gone would break its key's foreign key and fail
    # the whole migration at commit. Skip it: the table is dropped anyway.
    user_ids = frozenset(
        apps.get_model("auth", "User").objects.values_list("pk", flat=True)
    )
    # The key table is new in this migration and DRF allows one token per
    # user, so no two keys can share a digest or a user and name.
    api_key_model = apps.get_model("codex", "UserApiKey")
    api_key_model.objects.bulk_create(
        api_key_model(
            user_id=user_id,
            name=_UNIVERSAL_KEY_NAME,
            scope=_UNIVERSAL,
            prefix=secret[:_PREFIX_LENGTH],
            digest=_sha256(secret),
            kosync_digest=_md5(secret),
        )
        for secret, user_id in rows
        if secret and user_id in user_ids
    )
    schema_editor.execute(f"DROP TABLE IF EXISTS {_TOKEN_TABLE}")
    schema_editor.execute("DELETE FROM django_migrations WHERE app = 'authtoken'")


def tokens_to_api_keys(apps, schema_editor) -> None:
    """Migrate DRF tokens into keys and revoke the server-wide Stats API key."""
    _migrate_tokens(apps, schema_editor)
    apps.get_model("codex", "AdminFlag").objects.filter(key=_API_KEY_FLAG).delete()


class Migration(migrations.Migration):
    """Add KOReader hashes, shelves and API keys; fold in favorites and tokens."""

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("codex", "0059_remove_metron_legacy_login"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # KOReader sync.
        migrations.AddField(
            model_name="comic",
            name="koreader_hash",
            field=models.CharField(db_index=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="comic",
            name="koreader_name_hash",
            field=models.CharField(db_index=True, max_length=32, null=True),
        ),
        # Shelves.
        migrations.CreateModel(
            name="Shelf",
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
                ("name", models.CharField(max_length=128)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "shelves",
                "get_latest_by": "updated_at",
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="shelf",
            constraint=models.UniqueConstraint(
                fields=("user", "name"), name="unique_shelf_user_name"
            ),
        ),
        migrations.CreateModel(
            name="ShelfItem",
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
                    "collection",
                    models.CharField(
                        choices=[
                            ("publishers", "Publishers"),
                            ("imprints", "Imprints"),
                            ("series", "Series"),
                            ("volumes", "Volumes"),
                            ("folders", "Folders"),
                            ("arcs", "Story Arcs"),
                            ("comics", "Issues"),
                        ],
                        max_length=16,
                    ),
                ),
                ("target_id", models.PositiveIntegerField()),
                (
                    "shelf",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="codex.shelf",
                    ),
                ),
            ],
            options={
                "get_latest_by": "updated_at",
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="shelfitem",
            index=models.Index(
                fields=["collection", "target_id"], name="shelfitem_target"
            ),
        ),
        migrations.AddConstraint(
            model_name="shelfitem",
            constraint=models.UniqueConstraint(
                fields=("shelf", "collection", "target_id"),
                name="unique_shelfitem_shelf_target",
            ),
        ),
        migrations.AddField(
            model_name="settingsbrowserfilters",
            name="shelves",
            field=models.JSONField(default=list),
        ),
        # Widen the order_by choices to take ``shelved`` before the data
        # step rewrites stored ``favorite`` sort keys.
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
        migrations.AlterField(
            model_name="settingsdefaults",
            name="order_by",
            field=models.CharField(
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
                    ("shelved", "Shelved"),
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
        migrations.RunPython(favorites_to_shelves, shelves_to_favorites),
        migrations.RemoveField(
            model_name="settingsbrowserfilters",
            name="favorite",
        ),
        migrations.DeleteModel(
            name="Favorite",
        ),
        # API keys.
        migrations.CreateModel(
            name="UserApiKey",
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
                ("name", models.CharField(max_length=64)),
                ("prefix", models.CharField(max_length=4)),
                ("digest", models.CharField(max_length=64, unique=True)),
                ("kosync_digest", models.CharField(db_index=True, max_length=32)),
                ("last_used_at", models.DateTimeField(default=None, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_keys",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("device", "Device"),
                            ("universal", "Universal"),
                            ("stats", "Stats"),
                        ],
                        default="device",
                        max_length=9,
                    ),
                ),
            ],
            options={
                "verbose_name": "API key",
                "get_latest_by": "updated_at",
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "name"), name="unique_userapikey_user_name"
                    )
                ],
            },
        ),
        # The keys the tokens become go when the table does: nothing to undo.
        migrations.RunPython(tokens_to_api_keys, migrations.RunPython.noop),
        # Choice lists.
        migrations.AlterField(
            model_name="adminflag",
            name="key",
            field=models.CharField(
                choices=[
                    ("AA", "Anonymous User Age Rating"),
                    ("AR", "Age Rating Default"),
                    ("AU", "Auto Update"),
                    ("BT", "Banner Text"),
                    ("CM", "Custom Cover Max Upload Mb"),
                    ("FV", "Folder View"),
                    ("IM", "Import Metadata"),
                    ("KS", "Koreader Sync"),
                    ("LI", "Lazy Import Metadata"),
                    ("MP", "Browser Max Obj Per Page"),
                    ("NU", "Non Users"),
                    ("OP", "Opds"),
                    ("RG", "Registration"),
                    ("RV", "Register Verification"),
                    ("SA", "Stats Api"),
                    ("ST", "Send Telemetry"),
                ],
                db_index=True,
                max_length=2,
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
