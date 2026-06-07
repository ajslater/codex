"""
Tagging defaults, settings, custom-cover relink, rating rescale, group->collection.

A single migration carrying the v1.12.7 -> v2 schema and data changes.
* ``ComicboxTaggingDefaults`` singleton + seed.
* ``LibrarianStatus`` status-type choices.
* ``AdminFlag.key`` final choice set (adds RV, CM, MP, AK) + seeded MP/CM
  value rows. The choice edits are folded into one field redefinition
  because choices carry no DDL.
* Custom-cover schema (``Volume.custom_cover`` FK, ``V`` group choice,
  nullable ``CustomCover.library``) followed by a data migration that moves
  legacy cover files into ``uploads/``, detaches them from the synthetic
  covers-only ``Library``, and deletes it; then ``Library.covers_only`` is
  dropped.
* ``EmailSettings`` and ``ThrottleSettings`` singletons + seeds.
* API key moved from ``Timestamp`` (key ``AP``) to ``AdminFlag`` (key
  ``AK``); then ``Timestamp.version`` renamed to ``value``.
* ``Comic.critical_rating`` rescaled to the ComicInfo 0.0-5.0 scale, then
  the column shrunk to ``max_digits=2, decimal_places=1``.
* ``Comic.main_team`` foreign key repointed from ``Character`` to ``Team``
  (a copy-paste bug from ``main_character``).
* **Group -> collection unification**
  ``SettingsBrowserShow`` flag columns renamed ``p/i/s/v`` ->
  ``publishers/imprints/series/volumes``; ``Favorite.group``,
  ``CustomCover.group``, ``SettingsBrowser.top_group`` and
  ``SettingsBrowserLastRoute.group`` widened, their stored single-char codes
  data-migrated to collection names, then renamed to ``collection`` /
  ``top_collection`` (the dummy root ``0`` last-route sentinel is stripped
  going forward).

Operation order is load-bearing: ``move_api_key_to_admin_flag`` reads
``Timestamp.version`` so it runs before the rename; the custom-cover data
migration runs after its schema exists but before ``covers_only`` is
dropped; ``normalize_critical_ratings`` runs before the column is shrunk;
each group->collection field is widened and its char codes data-migrated
*before* the field is renamed to its collection name (the data steps still
read the legacy single-char codes).
"""

import contextlib
import shutil
from decimal import ROUND_HALF_UP, Decimal
from math import ceil, log10
from pathlib import Path

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from loguru import logger

import codex.models.fields
from codex.settings import (
    CUSTOM_COVERS_COLLECTION_DIRS,
    CUSTOM_COVERS_DIR,
    CUSTOM_COVERS_UPLOADS_DIR,
)

# ---------------------------------------------------------------------------
# ComicboxTaggingDefaults seed
# ---------------------------------------------------------------------------


def seed_comicbox_tagging_defaults(apps, _schema_editor):
    """Create the singleton ComicboxTaggingDefaults row."""
    comicbox_tagging_defaults = apps.get_model("codex", "ComicboxTaggingDefaults")
    comicbox_tagging_defaults.objects.get_or_create(
        pk=1,
        defaults={
            "default_formats": ["COMIC_INFO"],
            "default_sources": ["metron", "comicvine"],
        },
    )


# ---------------------------------------------------------------------------
# custom-cover file + library data migration
# ---------------------------------------------------------------------------

# Inline copy of the group-char map the live code uses, frozen at this
# migration's point in time. Live constants can drift; data migrations must
# replay deterministically against old DBs.
_GROUP_CHAR_TO_MODEL_NAME = {
    "p": "publisher",
    "i": "imprint",
    "s": "series",
    "v": "volume",
    "a": "storyarc",
    "f": "folder",
}


def _slugify(name: str) -> str:
    """Filesystem-safe slug derived from a group's sort_name."""
    if not name:
        return ""
    keep = []
    for ch in name.lower():
        if ch.isalnum():
            keep.append(ch)
        elif keep and keep[-1] != "-":
            keep.append("-")
    slug = "".join(keep).strip("-")
    return slug[:60]


def _resolve_slug(cover, apps) -> str:
    """Pick a human slug from the linked group, if any."""
    model_name = _GROUP_CHAR_TO_MODEL_NAME.get(cover.group)
    if not model_name:
        return ""
    model = apps.get_model("codex", model_name)
    linked = model.objects.filter(custom_cover_id=cover.pk).first()
    if linked is None:
        return ""
    raw = getattr(linked, "sort_name", "") or getattr(linked, "name", "") or ""
    return _slugify(str(raw))


def _new_cover_path(cover, slug: str) -> Path:
    """Build the new uploads/-rooted path for a cover row."""
    ext = Path(cover.path).suffix.lower() or ".jpg"
    stem = f"{cover.group}-{cover.pk}"
    if slug:
        stem = f"{stem}-{slug}"
    return CUSTOM_COVERS_UPLOADS_DIR / f"{stem}{ext}"


def _move_covers_to_uploads(apps) -> None:
    """Move legacy custom-cover files into the pk-keyed uploads dir."""
    custom_cover_model = apps.get_model("codex", "customcover")
    CUSTOM_COVERS_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for cover in custom_cover_model.objects.all():
        src = Path(cover.path)
        try:
            src.relative_to(CUSTOM_COVERS_UPLOADS_DIR)
        except ValueError:
            pass
        else:
            # Already under uploads/: just detach and continue.
            if cover.library_id is not None:
                cover.library = None
                cover.save(update_fields=["library"])
            continue

        if not src.is_file():
            logger.warning(f"Custom cover source file missing, skipping: {src}")
            cover.library = None
            cover.save(update_fields=["library"])
            continue

        slug = _resolve_slug(cover, apps)
        dest = _new_cover_path(cover, slug)
        try:
            shutil.move(str(src), str(dest))
        except OSError as exc:
            logger.warning(f"Failed to move custom cover {src} -> {dest}: {exc}")
            continue
        cover.path = str(dest)
        cover.library = None
        cover.save(update_fields=["path", "library"])


def _scrub_legacy_cover_dirs() -> None:
    """Best-effort: remove any leftover files under the legacy group dirs."""
    for group_dir in CUSTOM_COVERS_COLLECTION_DIRS:
        legacy = CUSTOM_COVERS_DIR / group_dir
        if not legacy.is_dir():
            continue
        for path in legacy.iterdir():
            if path.is_file():
                try:
                    path.unlink()
                except OSError as exc:
                    logger.warning(
                        f"Could not unlink legacy custom cover {path}: {exc}"
                    )
        with contextlib.suppress(OSError):
            legacy.rmdir()


def _delete_covers_only_library(apps) -> None:
    """Delete the synthetic covers-only Library row."""
    library_model = apps.get_model("codex", "library")
    library_model.objects.filter(covers_only=True).delete()


def migrate_custom_covers(apps, _schema_editor) -> None:
    """Move legacy custom covers to uploads/, detach + delete covers-only library."""
    _move_covers_to_uploads(apps)
    _scrub_legacy_cover_dirs()
    _delete_covers_only_library(apps)


# ---------------------------------------------------------------------------
# settings singletons
# ---------------------------------------------------------------------------


def seed_email_settings(apps, _schema_editor):
    """Create the EmailSettings singleton with model defaults (blank SMTP config)."""
    email_settings = apps.get_model("codex", "EmailSettings")
    email_settings.objects.get_or_create(pk=1)


def seed_throttle_settings(apps, _schema_editor):
    """Seed the ThrottleSettings singleton from current TOML/env values."""
    throttle_settings = apps.get_model("codex", "ThrottleSettings")
    throttle_settings.objects.get_or_create(
        pk=1,
        defaults={
            "anon": getattr(settings, "THROTTLE_ANON", 0) or 0,
            "user": getattr(settings, "THROTTLE_USER", 0) or 0,
            "opds": getattr(settings, "THROTTLE_OPDS", 0) or 0,
            "opensearch": getattr(settings, "THROTTLE_OPENSEARCH", 0) or 0,
            "reset_password": getattr(settings, "THROTTLE_RESET_PASSWORD", 5) or 0,
        },
    )


# ---------------------------------------------------------------------------
# AdminFlag MP / CM value-flag rows
# ---------------------------------------------------------------------------


def seed_value_flags(apps, _schema_editor):
    """Seed MP from settings and CM with the default upload cap."""
    admin_flag = apps.get_model("codex", "AdminFlag")
    mp_value = str(getattr(settings, "BROWSER_MAX_OBJ_PER_PAGE", 100) or 100)
    cm_value = str(getattr(settings, "CUSTOM_COVERS_MAX_UPLOAD_MB", 10) or 10)
    admin_flag.objects.update_or_create(
        key="MP",
        defaults={"on": True, "value": mp_value},
    )
    admin_flag.objects.update_or_create(
        key="CM",
        defaults={"on": True, "value": cm_value},
    )


# ---------------------------------------------------------------------------
# move API key Timestamp -> AdminFlag
# ---------------------------------------------------------------------------


def move_api_key_to_admin_flag(apps, _schema_editor):
    """Copy Timestamp.AP.version into AdminFlag.AK.value, then delete the row."""
    admin_flag = apps.get_model("codex", "AdminFlag")
    timestamp = apps.get_model("codex", "Timestamp")
    existing = timestamp.objects.filter(key="AP").first()
    api_key_value = existing.version if existing is not None else ""
    admin_flag.objects.update_or_create(
        key="AK",
        defaults={"on": True, "value": api_key_value},
    )
    if existing is not None:
        existing.delete()


def restore_api_key_to_timestamp(apps, _schema_editor):
    """Reverse: copy AdminFlag.AK back into a Timestamp.AP row."""
    admin_flag = apps.get_model("codex", "AdminFlag")
    timestamp = apps.get_model("codex", "Timestamp")
    flag = admin_flag.objects.filter(key="AK").first()
    api_key_value = flag.value if flag is not None else ""
    timestamp.objects.update_or_create(
        key="AP",
        defaults={"version": api_key_value},
    )
    if flag is not None:
        flag.delete()


# ---------------------------------------------------------------------------
# normalize Comic.critical_rating to the 0.0-5.0 scale
# ---------------------------------------------------------------------------

_ONE_DP = Decimal("0.1")
_MAX_RATING = Decimal("5.0")
_RATING_CHUNK_SIZE = 2000


def _normalize_rating(value):
    """Apply the comicbox-style CBI bucketing to a single rating."""
    if value is None:
        return None
    if value <= _MAX_RATING:
        return value.quantize(_ONE_DP, rounding=ROUND_HALF_UP)
    if value <= Decimal(10):
        divisor = Decimal(2)
    else:
        implied_max = Decimal(10) ** ceil(log10(float(value)))
        divisor = implied_max / _MAX_RATING
    result = (value / divisor).quantize(_ONE_DP, rounding=ROUND_HALF_UP)
    return min(result, _MAX_RATING)


def normalize_critical_ratings(apps, _schema_editor) -> None:
    """Rescale and quantize every non-null Comic.critical_rating."""
    comic_model = apps.get_model("codex", "comic")
    qs = comic_model.objects.exclude(critical_rating__isnull=True).only(
        "pk", "path", "critical_rating"
    )
    updates: list = []
    for comic in qs.iterator(chunk_size=_RATING_CHUNK_SIZE):
        before = comic.critical_rating
        after = _normalize_rating(before)
        if after == before:
            continue
        logger.info(f"critical_rating: {before} -> {after} ({comic.path})")
        comic.critical_rating = after
        updates.append(comic)
        if len(updates) >= _RATING_CHUNK_SIZE:
            comic_model.objects.bulk_update(updates, ("critical_rating",))
            updates = []
    if updates:
        comic_model.objects.bulk_update(updates, ("critical_rating",))


def _noop_reverse(_apps, _schema_editor) -> None:
    """No reverse: the rescale is intentionally lossy."""


# ===========================================================================
# Group -> Collection unification
# ===========================================================================
# Each char<->collection map and choices list is held inline, frozen at this
# migration's point in time, so the data moves replay deterministically
# against old DBs no matter how the live collection vocabulary drifts later.


# ---------------------------------------------------------------------------
# SettingsBrowser* group char -> collection value flip
# ---------------------------------------------------------------------------

_SB_CHAR_TO_COLLECTION = {
    "r": "root",
    "p": "publishers",
    "i": "imprints",
    "s": "series",
    "v": "volumes",
    "c": "comics",
    "f": "folders",
    "a": "arcs",
}
_SB_COLLECTION_TO_CHAR = {value: key for key, value in _SB_CHAR_TO_COLLECTION.items()}


def _remap_table_columns_keys(table_columns, value_map):
    """
    Remap a ``table_columns`` dict's top-collection keys through ``value_map``.

    ``table_columns`` is ``{top_collection: [column, ...]}``. Only the keys are
    char-coded; the column values are field names and pass through. Keys absent
    from ``value_map`` (already collection names, or unknown) are left as-is, so
    the move is idempotent and reversible.
    """
    if not table_columns:
        return table_columns
    return {value_map.get(key, key): columns for key, columns in table_columns.items()}


_TOP_GROUP_COLLECTION_CHOICES = [
    ("publishers", "Publishers"),
    ("imprints", "Imprints"),
    ("series", "Series"),
    ("volumes", "Volumes"),
    ("comics", "Issues"),
    ("folders", "Folders"),
    ("arcs", "Story Arcs"),
]
_ROUTE_COLLECTION_CHOICES = [*_TOP_GROUP_COLLECTION_CHOICES, ("root", "Root")]


def _sb_migrate_browser_rows(model, value_map) -> None:
    """
    Remap ``SettingsBrowser.top_group`` + ``table_columns`` keys via ``value_map``.

    Iterates every row — the active settings row *and* every named Saved View —
    so saved views keep their per-collection column config; only the char-coded
    keys flip to collection names.
    """
    for row in model.objects.all().iterator():
        update_fields = []
        mapped = value_map.get(row.top_group)
        if mapped and mapped != row.top_group:
            row.top_group = mapped
            update_fields.append("top_group")
        remapped = _remap_table_columns_keys(row.table_columns, value_map)
        if remapped != row.table_columns:
            row.table_columns = remapped
            update_fields.append("table_columns")
        if update_fields:
            row.save(update_fields=update_fields)


def _sb_migrate_last_route_row(row, value_map, *, to_collection: bool) -> None:
    """Remap one last-route row's group + strip the root 0 (forward only)."""
    update_fields = []
    mapped = value_map.get(row.group)
    if mapped not in (None, row.group):
        row.group = mapped
        update_fields.append("group")
    # Purge the dummy 0 root sentinel going forward; root is the empty list.
    stripped = [pk for pk in (row.pks or []) if pk]
    if to_collection and stripped != list(row.pks or []):
        row.pks = stripped
        update_fields.append("pks")
    if update_fields:
        row.save(update_fields=update_fields)


def _sb_migrate_last_route(model, value_map, *, to_collection: bool) -> None:
    """Remap ``SettingsBrowserLastRoute.group`` and strip the root 0 forward."""
    for row in model.objects.all().iterator():
        _sb_migrate_last_route_row(row, value_map, to_collection=to_collection)


def _sb_migrate_values(apps, *, to_collection: bool) -> None:
    """Map stored group chars <-> collection names (+ strip the root 0)."""
    value_map = _SB_CHAR_TO_COLLECTION if to_collection else _SB_COLLECTION_TO_CHAR
    _sb_migrate_browser_rows(apps.get_model("codex", "SettingsBrowser"), value_map)
    _sb_migrate_last_route(
        apps.get_model("codex", "SettingsBrowserLastRoute"),
        value_map,
        to_collection=to_collection,
    )


def migrate_settings_browser_groups_forward(apps, _schema_editor):
    """Map stored group chars -> collection names."""
    _sb_migrate_values(apps, to_collection=True)


def migrate_settings_browser_groups_reverse(apps, _schema_editor):
    """Map stored collection names -> group chars."""
    _sb_migrate_values(apps, to_collection=False)


# ---------------------------------------------------------------------------
# Favorite.group char -> collection value flip
# ---------------------------------------------------------------------------

_FAVORITE_CHAR_TO_COLLECTION = {
    "p": "publishers",
    "i": "imprints",
    "s": "series",
    "v": "volumes",
    "f": "folders",
    "a": "arcs",
    "c": "comics",
}
_FAVORITE_COLLECTION_TO_CHAR = {
    collection: char for char, collection in _FAVORITE_CHAR_TO_COLLECTION.items()
}

_FAVORITE_GROUP_CHOICES = [
    ("publishers", "Publishers"),
    ("imprints", "Imprints"),
    ("series", "Series"),
    ("volumes", "Volumes"),
    ("folders", "Folders"),
    ("arcs", "Story Arcs"),
    ("comics", "Issues"),
]


def favorite_groups_to_collections(apps, _schema_editor):
    """Rewrite each char-coded favorite group to its collection value."""
    favorite = apps.get_model("codex", "Favorite")
    for char, collection in _FAVORITE_CHAR_TO_COLLECTION.items():
        favorite.objects.filter(group=char).update(group=collection)


def favorite_collections_to_groups(apps, _schema_editor):
    """Reverse: rewrite collection values back to their char codes."""
    favorite = apps.get_model("codex", "Favorite")
    for collection, char in _FAVORITE_COLLECTION_TO_CHAR.items():
        favorite.objects.filter(group=collection).update(group=char)


# ---------------------------------------------------------------------------
# CustomCover.group char -> collection value flip
# ---------------------------------------------------------------------------

_CUSTOM_COVER_CHAR_TO_COLLECTION = {
    "p": "publishers",
    "i": "imprints",
    "s": "series",
    "v": "volumes",
    "a": "arcs",
    "f": "folders",
}
_CUSTOM_COVER_COLLECTION_TO_CHAR = {
    collection: char for char, collection in _CUSTOM_COVER_CHAR_TO_COLLECTION.items()
}

_CUSTOM_COVER_GROUP_CHOICES = [
    ("publishers", "Publishers"),
    ("imprints", "Imprints"),
    ("series", "Series"),
    ("volumes", "Volumes"),
    ("arcs", "Arcs"),
    ("folders", "Folders"),
]


def custom_cover_groups_to_collections(apps, _schema_editor):
    """Rewrite each char-coded custom-cover group to its collection value."""
    custom_cover = apps.get_model("codex", "CustomCover")
    for char, collection in _CUSTOM_COVER_CHAR_TO_COLLECTION.items():
        custom_cover.objects.filter(group=char).update(group=collection)


def custom_cover_collections_to_groups(apps, _schema_editor):
    """Reverse: rewrite collection values back to their char codes."""
    custom_cover = apps.get_model("codex", "CustomCover")
    for collection, char in _CUSTOM_COVER_COLLECTION_TO_CHAR.items():
        custom_cover.objects.filter(group=collection).update(group=char)


# ---------------------------------------------------------------------------
# AdminFlag BROWSER_DEFAULT_COLLECTION (BG) char -> collection value flip
# ---------------------------------------------------------------------------
# Migration 0039 seeds the BG flag with the legacy top-group char ("p"); flip
# it here alongside the per-user SettingsBrowser.top_collection it mirrors so a
# DB upgraded through this migration stores a valid collection name. These are
# exactly the seven BROWSER_TOP_COLLECTION_CHOICES keys (no "root" pseudo-row).

_BROWSER_DEFAULT_COLLECTION_KEY = "BG"
_BG_CHAR_TO_COLLECTION = {
    "p": "publishers",
    "i": "imprints",
    "s": "series",
    "v": "volumes",
    "c": "comics",
    "f": "folders",
    "a": "arcs",
}
_BG_COLLECTION_TO_CHAR = {
    collection: char for char, collection in _BG_CHAR_TO_COLLECTION.items()
}


def browser_default_flag_char_to_collection(apps, _schema_editor):
    """Rewrite the BG admin flag's char-coded value to its collection name."""
    admin_flag = apps.get_model("codex", "AdminFlag")
    for char, collection in _BG_CHAR_TO_COLLECTION.items():
        admin_flag.objects.filter(
            key=_BROWSER_DEFAULT_COLLECTION_KEY, value=char
        ).update(value=collection)


def browser_default_flag_collection_to_char(apps, _schema_editor):
    """Reverse: rewrite the BG admin flag's collection value back to its char."""
    admin_flag = apps.get_model("codex", "AdminFlag")
    for collection, char in _BG_COLLECTION_TO_CHAR.items():
        admin_flag.objects.filter(
            key=_BROWSER_DEFAULT_COLLECTION_KEY, value=collection
        ).update(value=char)


class Migration(migrations.Migration):
    """Consolidated v1.12.7 -> v2 schema and data migration."""

    dependencies = [
        ("codex", "0042_browser_table_view_and_favorites"),
    ]

    operations = [
        migrations.CreateModel(
            name="ComicboxTaggingDefaults",
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
                ("default_formats", models.JSONField(default=list)),
                ("delete_original", models.BooleanField(default=False)),
                (
                    "default_match_mode",
                    models.CharField(
                        choices=[
                            ("careful", "Careful"),
                            ("auto", "Auto"),
                            ("eager", "Eager"),
                        ],
                        default="auto",
                        max_length=32,
                    ),
                ),
                (
                    "default_prompts_mode",
                    models.CharField(
                        choices=[("ask", "Ask"), ("never", "Never")],
                        default="ask",
                        max_length=32,
                    ),
                ),
                ("default_sources", models.JSONField(default=list)),
                (
                    "metron_user",
                    codex.models.fields.EncryptedCharField(
                        blank=True, default="", max_length=512
                    ),
                ),
                (
                    "metron_password",
                    codex.models.fields.EncryptedCharField(
                        blank=True, default="", max_length=512
                    ),
                ),
                ("metron_url", models.URLField(blank=True, default="", max_length=256)),
                (
                    "comicvine_key",
                    codex.models.fields.EncryptedCharField(
                        blank=True, default="", max_length=512
                    ),
                ),
                (
                    "comicvine_url",
                    models.URLField(blank=True, default="", max_length=256),
                ),
            ],
            options={
                "verbose_name_plural": "ComicboxTaggingDefaults",
                "abstract": False,
                "get_latest_by": "updated_at",
            },
        ),
        migrations.RunPython(
            code=seed_comicbox_tagging_defaults,
            reverse_code=migrations.RunPython.noop,
        ),
        # --- LibrarianStatus status types ----------------------------
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
                    ("JID", "Check Integrity Of Entire Database"),
                    ("JIF", "Check Integrtity Of Database Foreign Keys"),
                    ("JIS", "Check Integrity Of Full Text Virtual Table"),
                    ("JLV", "Check Codex Latest Version"),
                    ("JRB", "Cleanup Orphan Bookmarks"),
                    ("JRF", "Cleanup Orphan Favorites"),
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
        # --- AdminFlag.key choices ---------
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
                    ("BG", "Browser Default Collection"),
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
        # --- custom-cover schema + data migration ------
        migrations.AddField(
            model_name="volume",
            name="custom_cover",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                to="codex.customcover",
            ),
        ),
        migrations.AlterField(
            model_name="customcover",
            name="group",
            field=models.CharField(
                choices=[
                    ("p", "P"),
                    ("i", "I"),
                    ("s", "S"),
                    ("v", "V"),
                    ("a", "A"),
                    ("f", "F"),
                ],
                db_index=True,
                max_length=1,
            ),
        ),
        migrations.AlterField(
            model_name="customcover",
            name="library",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="codex.library",
            ),
        ),
        migrations.RunPython(
            code=migrate_custom_covers,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="library",
            name="covers_only",
        ),
        # --- EmailSettings singleton ---------------------------------
        migrations.CreateModel(
            name="EmailSettings",
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
                ("host", models.CharField(blank=True, default="", max_length=128)),
                ("port", models.PositiveSmallIntegerField(default=587)),
                ("user", models.CharField(blank=True, default="", max_length=128)),
                (
                    "password",
                    codex.models.fields.EncryptedCharField(
                        blank=True, default="", max_length=512
                    ),
                ),
                ("use_tls", models.BooleanField(default=True)),
                ("use_ssl", models.BooleanField(default=False)),
                ("timeout", models.PositiveSmallIntegerField(default=10)),
                (
                    "from_address",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "subject_prefix",
                    models.CharField(blank=True, default="[Codex] ", max_length=32),
                ),
            ],
            options={
                "verbose_name_plural": "EmailSettings",
                "abstract": False,
                "get_latest_by": "updated_at",
            },
        ),
        migrations.RunPython(
            code=seed_email_settings,
            reverse_code=migrations.RunPython.noop,
        ),
        # --- ThrottleSettings singleton ------------------------------
        migrations.CreateModel(
            name="ThrottleSettings",
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
                ("anon", models.PositiveSmallIntegerField(default=0)),
                ("user", models.PositiveSmallIntegerField(default=0)),
                ("opds", models.PositiveSmallIntegerField(default=0)),
                ("opensearch", models.PositiveSmallIntegerField(default=0)),
                ("reset_password", models.PositiveSmallIntegerField(default=5)),
            ],
            options={
                "verbose_name_plural": "ThrottleSettings",
                "abstract": False,
                "get_latest_by": "updated_at",
            },
        ),
        migrations.RunPython(
            code=seed_throttle_settings,
            reverse_code=migrations.RunPython.noop,
        ),
        # --- seed value-flag rows (MP/CM) and move API key ----
        # move_api_key_to_admin_flag reads Timestamp.version, so it must run
        # before the version -> value rename below.
        migrations.RunPython(
            code=seed_value_flags,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            code=move_api_key_to_admin_flag,
            reverse_code=restore_api_key_to_timestamp,
        ),
        # --- Timestamp key choices + version -> value ---------
        migrations.AlterField(
            model_name="timestamp",
            name="key",
            field=models.CharField(
                choices=[
                    ("VR", "Codex Version"),
                    ("JA", "Janitor"),
                    ("TS", "Telemeter Sent"),
                    ("FI", "Failed Imports Seen"),
                ],
                db_index=True,
                max_length=2,
            ),
        ),
        migrations.RenameField(
            model_name="timestamp",
            old_name="version",
            new_name="value",
        ),
        migrations.AlterField(
            model_name="timestamp",
            name="value",
            field=models.CharField(default="", max_length=32),
        ),
        # --- normalize critical_rating then shrink the column --------
        migrations.RunPython(
            code=normalize_critical_ratings,
            reverse_code=_noop_reverse,
        ),
        migrations.AlterField(
            model_name="comic",
            name="critical_rating",
            field=codex.models.fields.CoercingDecimalField(  # pyright: ignore[reportCallIssue]  # ty: ignore[no-matching-overload]
                coerce_max=Decimal("5.0"),
                db_index=True,
                decimal_places=1,
                default=None,
                max_digits=2,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.0")),
                    django.core.validators.MaxValueValidator(Decimal("5.0")),
                ],
            ),
        ),
        # ``Comic.main_team`` was copy-pasted from ``main_character`` and
        # wrongly targeted ``Character``; repoint the FK at ``Team``. The
        # importer, serializers, and browser queries already treat it as a
        # team, so only the column's foreign-key target is corrected here.
        migrations.AlterField(
            model_name="comic",
            name="main_team",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="main_team_in_comics",
                to="codex.team",
            ),
        ),
        # ===================================================================
        # Group -> Collection unification
        # ===================================================================
        # The char->collection RunPython moves are load-bearing for real
        # <=0042 DBs that still hold single-char group codes; each field is
        # widened + data-migrated before it is renamed to its collection name.
        #
        # SettingsBrowserShow flag columns + SettingsBrowser.top_group /
        # SettingsBrowserLastRoute.group widen + char->collection data
        # (and strip the dummy root 0 sentinel).
        migrations.RemoveConstraint(
            model_name="settingsbrowsershow",
            name="unique_settingsbrowsershow_flags",
        ),
        migrations.RenameField(
            model_name="settingsbrowsershow", old_name="p", new_name="publishers"
        ),
        migrations.RenameField(
            model_name="settingsbrowsershow", old_name="i", new_name="imprints"
        ),
        migrations.RenameField(
            model_name="settingsbrowsershow", old_name="s", new_name="series"
        ),
        migrations.RenameField(
            model_name="settingsbrowsershow", old_name="v", new_name="volumes"
        ),
        migrations.AddConstraint(
            model_name="settingsbrowsershow",
            constraint=models.UniqueConstraint(
                fields=("publishers", "imprints", "series", "volumes"),
                name="unique_settingsbrowsershow_flags",
            ),
        ),
        migrations.AlterField(
            model_name="settingsbrowser",
            name="top_group",
            field=models.CharField(
                choices=_TOP_GROUP_COLLECTION_CHOICES,
                default="publishers",
                max_length=32,
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
                    ("metadata_mtime", "Tags Updated"),
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
        migrations.AlterField(
            model_name="settingsbrowserlastroute",
            name="group",
            field=models.CharField(
                choices=_ROUTE_COLLECTION_CHOICES, default="root", max_length=32
            ),
        ),
        migrations.RunPython(
            code=migrate_settings_browser_groups_forward,
            reverse_code=migrate_settings_browser_groups_reverse,
        ),
        # The BROWSER_DEFAULT_COLLECTION (BG) admin flag mirrors
        # SettingsBrowser.top_collection; flip its seeded char value too.
        migrations.RunPython(
            code=browser_default_flag_char_to_collection,
            reverse_code=browser_default_flag_collection_to_char,
        ),
        # Widen Favorite.group, then char->collection data move.
        migrations.AlterField(
            model_name="favorite",
            name="group",
            field=models.CharField(choices=_FAVORITE_GROUP_CHOICES, max_length=16),
        ),
        migrations.RunPython(
            code=favorite_groups_to_collections,
            reverse_code=favorite_collections_to_groups,
        ),
        # Widen CustomCover.group, then char->collection data move.
        migrations.AlterField(
            model_name="customcover",
            name="group",
            field=models.CharField(
                choices=_CUSTOM_COVER_GROUP_CHOICES, db_index=True, max_length=10
            ),
        ),
        migrations.RunPython(
            code=custom_cover_groups_to_collections,
            reverse_code=custom_cover_collections_to_groups,
        ),
        migrations.RenameField(
            model_name="favorite",
            old_name="group",
            new_name="collection",
        ),
        migrations.AlterUniqueTogether(
            name="favorite",
            unique_together={("user", "collection", "target_id")},
        ),
        migrations.RenameField(
            model_name="customcover",
            old_name="group",
            new_name="collection",
        ),
        migrations.RenameField(
            model_name="settingsbrowserlastroute",
            old_name="group",
            new_name="collection",
        ),
        migrations.RenameField(
            model_name="settingsbrowser",
            old_name="top_group",
            new_name="top_collection",
        ),
    ]
