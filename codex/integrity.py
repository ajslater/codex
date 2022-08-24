"""Repair Database Integrity Errors."""
import os
import re
import sqlite3

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.db.migrations.recorder import MigrationRecorder
from django.db.models.functions import Now
from django.db.utils import OperationalError

from codex.settings.logging import get_logger
from codex.settings.settings import CONFIG_PATH, DB_PATH


NO_0005_ARG = "no_0005"
OK_EXC_ARGS = (NO_0005_ARG, "no such table: django_migrations")
REPAIR_FLAG_PATH = CONFIG_PATH / "rebuild_db"
DUMP_LINE_MATCHER = re.compile("TRANSACTION|ROLLBACK|COMMIT")
REBUILT_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".rebuilt")
BACKUP_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".backup")
MIGRATION_0005 = "0005_auto_20200918_0146"
MIGRATION_0007 = "0007_auto_20211210_1710"
MIGRATION_0010 = "0010_haystack"
MIGRATION_0011 = "0010_library_groups_and_metadata_changes"
MIGRATION_0018 = "0018_rename_userbookmark_bookmark"
M2M_NAMES = {
    "Character": "characters",
    "Credit": "credits",
    "Genre": "genres",
    "Location": "locations",
    "SeriesGroup": "series_groups",
    "StoryArc": "story_arcs",
    "Tag": "tags",
    "Team": "teams",
    "Folder": "folders",
}
NULL_SET = frozenset([None])
HAVE_LIBRARY_FKS = ("FailedImport", "Folder", "Comic")
GROUP_HOSTS = {
    "Imprint": ("Publisher",),
    "Series": ("Publisher", "Imprint"),
    "Volume": ("Publisher", "Imprint", "Series"),
    "Comic": ("Publisher", "Imprint", "Series", "Volume"),
}
WATCHED_PATHS = ("Comic", "Folder")
CREDIT_FIELDS = {"CreditRole": "role", "CreditPerson": "person"}
OPERATIONAL_ERRORS_BEFORE_MIGRATIONS = (
    "no such column: codex_comic.name",
    "no such column: codex_comic.stat",
    "no such column: codex_folder.stat",
    "no such table: codex_comic_folders",
    "'QuerySet' object has no attribute 'stat'",
)
DELETE_BAD_COMIC_FOLDER_RELATIONS_SQL = (
    'DELETE FROM "codex_comic_folder" '
    'WHERE (NOT ("codex_comic_folder"."comic_id" '
    'IN (SELECT "codex_comic"."id" FROM "codex_comic")) '
    'OR NOT ("codex_comic_folder"."folder_id" '
    'IN (SELECT "codex_folder"."id" FROM "codex_folder")))'
)
LOG = get_logger(__name__)


def has_applied_migration(migration_name):
    """Check if a specific migration has been applied."""
    return MigrationRecorder.Migration.objects.filter(
        app="codex", name=migration_name
    ).exists()


def _repair_old_comic_folder_fks():
    if has_applied_migration(MIGRATION_0007):
        return
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute(DELETE_BAD_COMIC_FOLDER_RELATIONS_SQL)
        LOG.verbose("Deleted old comic_folder relations with bad integrity.")
    except Exception as exc:
        LOG.exception(exc)


def _fix_comic_m2m_integrity_errors(apps, comic_model, m2m_model_name, field_name):
    """Fix Comic ManyToMany integrity errors."""
    """Delete relations to comics that don't exist and m2ms that don't exist."""
    m2m_model = apps.get_model("codex", m2m_model_name)
    field = getattr(comic_model, field_name)
    through_model = field.through  # noqa: N806
    link_col = field_name[:-1].replace("_", "") + "_id"

    m2m_rels_with_bad_comic_ids = through_model.objects.exclude(
        comic_id__in=comic_model.objects.all()
    )
    count_comic, _ = m2m_rels_with_bad_comic_ids.delete()
    m2m_rels_with_bad_m2m_ids = through_model.objects.exclude(
        **{f"{link_col}__in": m2m_model.objects.all()}
    )
    bad_comics = comic_model.objects.filter(
        pk__in=m2m_rels_with_bad_m2m_ids.values_list("comic_id", flat=True)
    )
    count_m2m, _ = m2m_rels_with_bad_m2m_ids.delete()
    count = count_comic + count_m2m
    if count:
        LOG.verbose(f"Deleted {count} orphan relations to {field_name}")
    return bad_comics


def _mark_comics_with_bad_m2m_rels_for_update(comic_model, bad_comics):
    """Mark affected comics for update."""
    try:
        update_comics = []

        for comic in bad_comics.values("pk", "stat"):
            stat_list = comic.stat
            if not stat_list:
                continue
            stat_list[8] = 0.0
            comic.stat = stat_list
            update_comics.append(comic)

        if not update_comics:
            return

        count = comic_model.objects.bulk_update(update_comics, fields=["stat"])
        LOG.info(f"Marked {count} comics with bad m2m relations for update by poller.")
    except (OperationalError, AttributeError) as exc:
        ok = False
        for arg in exc.args:
            if arg in OPERATIONAL_ERRORS_BEFORE_MIGRATIONS:
                LOG.debug(
                    "Can't mark modified comics for update, "
                    "but if this happens right before migration 0007, "
                    "they'll be updated anyway."
                )
                ok = True
        if not ok:
            LOG.exception(exc)


def _find_fk_integrity_errors_with_models(
    host_model, fk_model, fk_field_name, log=True
):
    """Find foreign key integrity errors with specified models."""
    inner_qs = fk_model.objects.all()
    exclude_filter = {f"{fk_field_name}__in": inner_qs}
    invalid_host_objs = host_model.objects.exclude(**exclude_filter).only(fk_field_name)
    if fk_field_name in ("parent_folder", "role"):
        # Special fields can be null
        # THIS IS VERY IMPORTANT TO AVOID DELETING ALL TOP LEVEL FOLDERS
        not_null_filter = {f"{fk_field_name}__isnull": False}
        invalid_host_objs = invalid_host_objs.filter(**not_null_filter)

    count = invalid_host_objs.count()
    if count and log:
        LOG.verbose(f"Found {host_model.__name__}s with bad {fk_field_name}: {count}")
    return invalid_host_objs


def _find_fk_integrity_errors(apps, host_model_name, fk_model_name, fk_field_name):
    """Find foreign key integrity errors."""
    host_model = apps.get_model("codex", host_model_name)
    fk_model = apps.get_model("codex", fk_model_name)
    return _find_fk_integrity_errors_with_models(host_model, fk_model, fk_field_name)


def _delete_query(query, host_model_name, fk_model_name):
    """Execute the delete on the query."""
    count, _ = query.delete()
    if count:
        LOG.info(f"Deleted {count} {host_model_name}s in nonextant {fk_model_name}s.")


def _delete_fk_integrity_errors(apps, host_model_name, fk_model_name, fk_field_name):
    """Delete objects with bad integrity."""
    try:
        bad_host_objs = _find_fk_integrity_errors(
            apps, host_model_name, fk_model_name, fk_field_name
        )
        _delete_query(bad_host_objs, host_model_name, fk_model_name)
    except OperationalError as exc:
        ok = False
        for arg in exc.args:
            if arg in OPERATIONAL_ERRORS_BEFORE_MIGRATIONS:
                ok = True
        if not ok:
            LOG.exception(exc)
    except Exception as exc:
        LOG.exception(exc)


def _null_missing_fk(host_model, fk_model, fk_field_name):
    """Set missing fks to null."""
    query_missing_fks = _find_fk_integrity_errors_with_models(
        host_model, fk_model, fk_field_name, log=False
    )
    not_null_filter = {f"{fk_field_name}__isnull": False}
    query_missing_fks = query_missing_fks.filter(**not_null_filter)
    count = query_missing_fks.count()
    if count:
        update_dict = {fk_field_name: None, "updated_at": Now()}
        query_missing_fks.update(**update_dict)
        LOG.verbose(
            f"Fixed {count} {host_model.__name__}s with missing {fk_field_name}"
        )


def _delete_bookmark_integrity_errors(apps):
    """Fix Bookmarks with non codex model fields."""
    if not has_applied_migration(MIGRATION_0018):
        return
    # Bookmarks that don't reference a valid comic are useless.
    _delete_fk_integrity_errors(apps, "Bookmark", "Comic", "comic")

    # Bookmarks that aren't linked to a valid session or a user are orphans
    bm_model = apps.get_model("codex", "Bookmark")
    _null_missing_fk(bm_model, Session, "session")
    _null_missing_fk(bm_model, get_user_model(), "user")
    orphan_bms = bm_model.objects.filter(session=None, user=None)
    _delete_query(orphan_bms, "Bookmark", "session or user")


def _delete_search_result_fk_errors(apps):
    """Fix SearcResults with non valid fields."""
    if not has_applied_migration(MIGRATION_0010):
        return
    comic_model = apps.get_model("codex", "comic")
    search_query_model = apps.get_model("codex", "searchquery")
    valid_comics = comic_model.objects.all()
    valid_queries = search_query_model.objects.all()
    search_result_model = apps.get_model("codex", "searchresult")
    orphan_srs = search_result_model.objects.exclude(
        query__in=valid_queries, comic__in=valid_comics
    )
    count, _ = orphan_srs.delete()
    if count:
        LOG.verbose(f"Deleted {count} orphan SearchResults")


def _repair_library_groups(apps):
    """Remove non-extant groups from libraries."""
    if not has_applied_migration(MIGRATION_0011):
        return
    library_model = apps.get_model("codex", "library")
    through_model = library_model.groups.through
    valid_groups = Group.objects.all()
    bad_relations = through_model.objects.exclude(group_id__in=valid_groups)
    bad_relations.delete()


def _fix_db_integrity():
    """Fix most of the Codex model integrity errors we can."""
    LOG.verbose("Reparing database integrity...")
    # DELETE things we can't fix
    for host_model_name in HAVE_LIBRARY_FKS:
        _delete_fk_integrity_errors(apps, host_model_name, "Library", "library")

    for host_model_name in WATCHED_PATHS:
        _delete_fk_integrity_errors(apps, host_model_name, "Folder", "parent_folder")

    for host_model_name, groups in GROUP_HOSTS.items():
        for group_model_name in groups:
            group_field_name = group_model_name.lower()
            _delete_fk_integrity_errors(
                apps, host_model_name, group_model_name, group_field_name
            )

    for fk_model_name, fk_field_name in CREDIT_FIELDS.items():
        _delete_fk_integrity_errors(apps, "Credit", fk_model_name, fk_field_name)

    _delete_bookmark_integrity_errors(apps)

    _repair_old_comic_folder_fks()

    # REPAIR the objects that are left
    comic_model = apps.get_model("codex", "Comic")
    bad_comic_ids = comic_model.objects.none()
    for m2m2_model_name, field_name in M2M_NAMES.items():
        try:
            bad_comic_ids |= _fix_comic_m2m_integrity_errors(
                apps, comic_model, m2m2_model_name, field_name
            )
        except OperationalError as exc:
            ok = False
            for arg in exc.args:
                if arg in OPERATIONAL_ERRORS_BEFORE_MIGRATIONS:
                    ok = True
            if ok:
                LOG.verbose(
                    "Couldn't look for comics with folder integrity problems before "
                    "migration 0007. We'll get them on the next restart."
                )
            else:
                LOG.exception(exc)
    _mark_comics_with_bad_m2m_rels_for_update(comic_model, bad_comic_ids)

    _delete_search_result_fk_errors(apps)

    _repair_library_groups(apps)

    LOG.verbose("Done with database integrity check.")


def repair_db():
    """Fix the db but trap errors if it goes wrong."""
    try:
        if os.environ.get("CODEX_SKIP_INTEGRITY_CHECK"):
            LOG.info("Skipping integrity check")
            return

        if not has_applied_migration(MIGRATION_0005):
            raise OperationalError(NO_0005_ARG)
        _fix_db_integrity()
    except OperationalError as exc:
        ok = False
        for arg in exc.args:
            if arg in OK_EXC_ARGS:
                ok = True
                LOG.verbose(
                    f"Not running integrity checks until migration {MIGRATION_0005}"
                    " has been applied."
                )
                break
        if not ok:
            LOG.exception(exc)
    except Exception as exc:
        LOG.exception(exc)


def rebuild_db():
    """Dump and rebuild the database."""
    # Drastic
    if not REPAIR_FLAG_PATH.exists():
        return

    LOG.warning("REBUILDING DATABASE!!")
    with sqlite3.connect(REBUILT_DB_PATH) as new_db_conn:
        new_db_cur = new_db_conn.cursor()
        with sqlite3.connect(DB_PATH) as old_db_conn:
            for line in old_db_conn.iterdump():
                if DUMP_LINE_MATCHER.search(line):
                    continue
                new_db_cur.execute(line)

    DB_PATH.rename(BACKUP_DB_PATH)
    LOG.info("Backed up old db to %s", BACKUP_DB_PATH)
    REBUILT_DB_PATH.replace(DB_PATH)
    REPAIR_FLAG_PATH.unlink(missing_ok=True)
    LOG.info("Rebuilt database.")
