"""Repair Database Integrity Errors."""
import os
import re
import sqlite3

from itertools import chain
from logging import getLogger

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Q
from django.db.models.functions import Now
from django.db.utils import OperationalError

from codex.librarian.db.query_fks import FILTER_ARG_MAX
from codex.settings.settings import CONFIG_PATH, DB_PATH


NO_0005_ARG = "no_0005"
OK_EXC_ARGS = (NO_0005_ARG, "no such table: django_migrations")
REPAIR_FLAG_PATH = CONFIG_PATH / "rebuild_db"
DUMP_LINE_MATCHER = re.compile("TRANSACTION|ROLLBACK|COMMIT")
REBUILT_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".rebuilt")
BACKUP_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".backup")
MIGRATION_0005 = "0005_auto_20200918_0146"
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
NULL_SET = set([None])
HAVE_LIBRARY_FKS = ("FailedImport", "Folder", "Comic")
GROUP_HOSTS = {
    "Imprint": ("Publisher",),
    "Series": ("Publisher", "Imprint"),
    "Volume": ("Publisher", "Imprint", "Series"),
    "Comic": ("Publisher", "Imprint", "Series", "Volume"),
}
WATCHED_PATHS = ("Comic", "Folder")
CREDIT_FIELDS = {"CreditRole": "role", "CreditPerson": "person"}
LOG = getLogger(__name__)


def _get_invalid_m2m_ids(comic_model, m2m_model, field_name):
    """Query for invalid_m2m_ids."""
    comic_m2m_ids = set(
        comic_model.objects.all().values_list(f"{field_name}__id", flat=True)
    )
    valid_m2m_ids = set(m2m_model.objects.all().values_list("pk", flat=True))
    invalid_m2m_ids = comic_m2m_ids - valid_m2m_ids - set([None])
    if num_invalid_m2m_ids := len(invalid_m2m_ids):
        LOG.verbose(  # type: ignore
            f"Comic.{field_name} - valid: {len(valid_m2m_ids)},"
            f" invalid: {num_invalid_m2m_ids}"
        )
    return invalid_m2m_ids


def _batch_filter_args(iterable):
    """Generate batches of filter args to not break sqlite."""
    len_iterable = len(iterable)
    for index in range(0, len_iterable, FILTER_ARG_MAX):
        yield list(iterable)[index : min(index + FILTER_ARG_MAX, len_iterable)]


def _delete_invalid_m2m_rels(comic_model, m2m_model, field_name, invalid_m2m_ids):
    """Delete the bad m2m relations."""
    field = getattr(comic_model, field_name)
    ThroughModel = field.through  # noqa: N806

    link_name = m2m_model.__name__.lower()
    bad_comic_ids = set()
    total_count = 0
    batch_count = 0
    num_invalid_m2m_ids = len(invalid_m2m_ids)
    for invalid_m2m_ids_batch in _batch_filter_args(invalid_m2m_ids):
        try:
            batch_count += len(invalid_m2m_ids_batch)
            filter_args = {f"{link_name}_id__in": invalid_m2m_ids_batch}
            query = ThroughModel.objects.filter(**filter_args)
            bad_comic_ids |= set(query.values_list("comic_id", flat=True))
            total_count += query.count()
            query.delete()
            LOG.debug(f"deleted {field_name} batch {batch_count}/{num_invalid_m2m_ids}")
        except Exception as exc:
            LOG.warning(exc)
    LOG.info(
        f"Deleted {total_count} relations from {len(bad_comic_ids)} "
        f"comics to missing {field_name}."
    )
    return bad_comic_ids


def _mark_comics_with_bad_m2m_rels_for_update(comic_model, field_name, bad_comic_ids):
    """Mark affected comics for update."""
    all_bad_comics = []
    num_all_bad_comics = 0
    try:
        batch_count = 0
        num_bad_comic_ids = len(bad_comic_ids)
        for bad_comic_ids_batch in _batch_filter_args(bad_comic_ids):
            filter = Q(pk__in=bad_comic_ids_batch)
            bad_comics = comic_model.objects.filter(filter).only("pk", "stat")
            all_bad_comics.append(bad_comics)
            num_all_bad_comics += bad_comics.count()
            LOG.debug(
                f"found bad comics batch {batch_count}/{num_bad_comic_ids} "
                f"with bad {field_name}"
            )

        if not num_all_bad_comics:
            return
        LOG.verbose(  # type: ignore
            f"Found {num_all_bad_comics} comics with bad {field_name}."
        )

        update_comics = []

        for comic in chain(all_bad_comics):
            stat_list = comic.stat
            if not stat_list:
                continue
            stat_list[8] = 0.0
            comic.stat = stat_list
            update_comics.append(comic)

        if not update_comics:
            return

        count = comic_model.objects.bulk_update(update_comics, fields=["stat"])
        LOG.info(f"Marked {count} with missing {field_name} for update by poller.")
    except (OperationalError, AttributeError) as exc:
        if (
            "no such column: codex_comic.stat" in exc.args
            or "'QuerySet' object has no attribute 'stat'" in exc.args
        ):
            LOG.debug(
                "Can't mark modified comics for update, "
                "but if this happens right before migration 0007, "
                "they'll be updated anyway."
            )
        else:
            LOG.exception(exc)


def _fix_comic_m2m_integrity_errors(apps, m2m_model_name, field_name):
    """Fix Comic ManyToMany integrity errors."""
    comic_model = apps.get_model("codex", "Comic")
    m2m_model = apps.get_model("codex", m2m_model_name)

    invalid_m2m_ids = _get_invalid_m2m_ids(comic_model, m2m_model, field_name)
    if not len(invalid_m2m_ids):
        return

    bad_comic_ids = _delete_invalid_m2m_rels(
        comic_model, m2m_model, field_name, invalid_m2m_ids
    )

    _mark_comics_with_bad_m2m_rels_for_update(comic_model, field_name, bad_comic_ids)


def _find_fk_integrity_errors_with_models(
    host_model, fk_model, fk_field_name, log=True
):
    """Find foreign key integrity errors with specified models."""
    inner_qs = fk_model.objects.all()
    exclude_filter = {f"{fk_field_name}__in": inner_qs}
    invalid_host_objs = host_model.objects.exclude(**exclude_filter)
    if fk_field_name in ("parent_folder", "role"):
        # Special fields can be null
        # THIS IS VERY IMPORTANT TO AVOID DELETING ALL TOP LEVEL FOLDERS
        not_null_filter = {f"{fk_field_name}__isnull": False}
        invalid_host_objs = invalid_host_objs.filter(**not_null_filter)

    count = invalid_host_objs.count()
    if count and log:
        LOG.verbose(  # type: ignore
            f"Found {host_model.__name__}s with bad {fk_field_name}: {count}"
        )
    return invalid_host_objs


def _find_fk_integrity_errors(apps, host_model_name, fk_model_name, fk_field_name):
    """Find foreign key integrity errors."""
    host_model = apps.get_model("codex", host_model_name)
    fk_model = apps.get_model("codex", fk_model_name)
    return _find_fk_integrity_errors_with_models(host_model, fk_model, fk_field_name)


def _delete_query(query, host_model_name, fk_model_name):
    """Execute the delete on the query."""
    if num_bad := query.count():
        query.delete()
        LOG.info(f"Deleted {num_bad} {host_model_name}s in nonextant {fk_model_name}s.")


def _delete_fk_integrity_errors(apps, host_model_name, fk_model_name, fk_field_name):
    """Delete objects with bad integrity."""
    try:
        bad_host_objs = _find_fk_integrity_errors(
            apps, host_model_name, fk_model_name, fk_field_name
        )
        _delete_query(bad_host_objs, host_model_name, fk_model_name)
    except Exception as exc:
        LOG.warning(exc)


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
        LOG.verbose(  # type: ignore
            f"Fixed {count} {host_model.__name__}s with missing {fk_field_name}"
        )


def _delete_userbookmark_integrity_errors(apps):
    """Fix UserBookmarks with non codex model fields."""
    # UserBookmarks that don't reference a valid comic are useless.
    _delete_fk_integrity_errors(apps, "UserBookmark", "Comic", "comic")

    # UserBookmarks that aren't linked to a valid session or a user are orphans
    ubm_model = apps.get_model("codex", "UserBookmark")
    _null_missing_fk(ubm_model, Session, "session")
    _null_missing_fk(ubm_model, get_user_model(), "user")
    orphan_ubms = ubm_model.objects.filter(session=None, user=None)
    _delete_query(orphan_ubms, "UserBookmark", "session or user")


def _fix_db_integrity():
    """Fix most of the Codex model integrity errors we can."""
    LOG.verbose("Reparing database integrity...")  # type: ignore
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

    _delete_userbookmark_integrity_errors(apps)

    # REPAIR the objects that are left
    for m2m2_model_name, field_name in M2M_NAMES.items():
        try:
            _fix_comic_m2m_integrity_errors(apps, m2m2_model_name, field_name)
        except OperationalError as exc:
            if "no such table: codex_comic_folders" in exc.args:
                LOG.debug(
                    "Couldn't look for comics with folder integrity problems before "
                    "migration 0007. We'll get them on the next restart."
                )
            else:
                LOG.exception(exc)
            LOG.warning(exc)

    LOG.verbose("Done with database integrity check.")  # type: ignore


def repair_db():
    """Fix the db but trap errors if it goes wrong."""
    try:
        if os.environ.get("CODEX_SKIP_INTEGRITY_CHECK"):
            LOG.info("Skipping integrity check")
            return
        ready = MigrationRecorder.Migration.objects.filter(
            app="codex", name=MIGRATION_0005
        ).exists()
        if not ready:
            raise OperationalError(NO_0005_ARG)
        _fix_db_integrity()
    except OperationalError as exc:
        ok = False
        for arg in exc.args:
            if arg in OK_EXC_ARGS:
                ok = True
                LOG.verbose(  # type: ignore
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
