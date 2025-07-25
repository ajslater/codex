"""Database integrity checks and remedies."""
# Uses app.get_model() because functions may also be called before the models are ready on startup.

import re
from typing import TYPE_CHECKING

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models.functions import Now
from django.db.utils import OperationalError

from codex.librarian.scribe.janitor.status import (
    JanitorDBFKIntegrityStatus,
    JanitorDBFTSIntegrityStatus,
    JanitorDBFTSRebuildStatus,
    JanitorDBIntegrityStatus,
)
from codex.librarian.scribe.janitor.tasks import JanitorFTSRebuildTask
from codex.librarian.worker import WorkerStatusMixin
from codex.models.base import BaseModel
from codex.settings import (
    CONFIG_PATH,
    CUSTOM_COVERS_DIR,
    DB_PATH,
)

if TYPE_CHECKING:
    from django.db.models.manager import BaseManager

    from codex.models.comic import Comic


REPAIR_FLAG_PATH = CONFIG_PATH / "rebuild_db"
REBUILT_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".rebuilt")
BACKUP_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".bak")
DUMP_LINE_MATCHER = re.compile("TRANSACTION|ROLLBACK|COMMIT")


_FTS_INSERT_TMPL = "INSERT INTO codex_comicfts (codex_comicfts) VALUES('%s');"
_PRAGMA_TMPL = "PRAGMA %s;"


def _exec_sql(sql):
    """Run sql on an potentially unready database.."""
    connection = connections[DEFAULT_DB_ALIAS]
    connection.prepare_database()
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cursor.execute(sql)
        return cursor.fetchall()


def _compile_foreign_key_results(results, log):
    bad_fk_rels = {}
    bad_m2m_rows = {}

    for row in results:
        table_name, rowid, _parent, fkid = row
        if fkid:
            if table_name not in bad_fk_rels:
                bad_fk_rels[table_name] = {}
            if rowid not in bad_fk_rels[table_name]:
                bad_fk_rels[table_name][rowid] = set()
            bad_fk_rels[table_name][rowid].add(fkid)
        else:
            if table_name not in bad_m2m_rows:
                bad_m2m_rows[table_name] = set()
            bad_m2m_rows[table_name].add(rowid)

    if bad_fk_rels:
        log.debug(f"Found {len(bad_fk_rels)} tables with illegal foreign keys.")
    if bad_m2m_rows:
        log.debug(
            f"Found {len(bad_m2m_rows)} many to many through tables with illegal relations."
        )

    return bad_fk_rels, bad_m2m_rows


def _get_model(table_name) -> type[BaseModel]:
    """Get a django model from the table name."""
    app_name, model_name = table_name.split("_", 1)
    app_config = apps.get_app_config(app_name)
    try:
        from_rel_model_name, to_rel_model_name = model_name.split("_", 1)
    except ValueError:
        from_rel_model_name = to_rel_model_name = ""
    model: type[BaseModel]
    if from_rel_model_name in ("comic", "library"):
        # Use the from model to create an m2m through model because I don't know a simpler way.
        from_model = app_config.get_model(from_rel_model_name)
        field_name = to_rel_model_name.replace("_", "")
        model = getattr(from_model, field_name).through
    else:
        # Not an m2m through model.
        model_name = model_name.replace("_", "")
        model = app_config.get_model(model_name)  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
    return model


def _null_bad_fk_rels_table(table_name, bad_rows, log):
    """Null bad foreign key relations by table."""
    fix_comic_pks = set()
    model: type[BaseModel] = _get_model(table_name)
    fields = model._meta.fields
    field_names = {}
    update_objs = []
    objs: BaseManager[BaseModel] = model.objects.filter(pk__in=bad_rows.keys())
    update_fields = {"updated_at"}
    now = Now()
    for obj in objs:
        try:
            fkids = bad_rows.get(obj.pk)
            if not fkids:
                continue
            for fkid in fkids:
                if fkid not in field_names:
                    field_names[fkid] = fields[fkid].name
                field_name = field_names[fkid]
                setattr(obj, field_name, None)
                update_fields.add(field_name)
            obj.updated_at = now
            update_objs.append(obj)
        except Exception as exc:
            log.warning(
                f"Unable to null bad foreign keys in {table_name}:{obj.pk} - {exc}"
            )
        if table_name == "comic":
            fix_comic_pks.add(obj.pk)

    if update_objs:
        model.objects.bulk_update(update_objs, sorted(update_fields))
        log.info(
            f"Removed illegal foreign key relations from {len(update_objs)} {table_name}s"
        )
    return fix_comic_pks


def _null_bad_fk_rels(bad_fk_rels, log):
    """Null bad foreign key relations."""
    fix_comic_pks = set()
    for table_name, bad_rows in bad_fk_rels.items():
        try:
            fix_comic_pks |= _null_bad_fk_rels_table(table_name, bad_rows, log)
        except Exception:
            pks = sorted(bad_rows.keys())
            log.exception(
                f"Unable to null {len(pks)} {table_name} rows with bad foreign keys"
            )
            log.error(f"{table_name}: {pks}")  # noqa: TRY400
    return fix_comic_pks


def _delete_bad_m2m_rows_table(table_name, ids, fix_comic_pks, log):
    """Delete illegal foreign keys for one table."""
    model = _get_model(table_name)

    qs = model.objects.filter(id__in=ids)
    try:
        comic_ids = qs.values_list("comic_id", flat=True)
        fix_comic_pks |= set(comic_ids)
    except (OperationalError, AttributeError):
        log.exception("Add comic ids to fix list.")

    count, _ = qs.delete()
    level = "INFO" if count else "DEBUG"
    log.log(level, f"Deleted {count} {table_name} rows that failed integrity check.")
    return count


def _delete_bad_m2m_rows(bad_m2m_rows, log):
    """Delete illegal foreign keys for all tables."""
    fix_comic_pks = set()
    count = 0
    for table_name, ids in bad_m2m_rows.items():
        try:
            count += _delete_bad_m2m_rows_table(table_name, ids, fix_comic_pks, log)
        except Exception:
            log.exception(f"Could not delete bad foreign keys in table {table_name}")
    if count:
        log.info(f"Removed {count} bad foreign key relations.")
    return fix_comic_pks


def _mark_comics_for_update(fix_comic_pks, log):
    """Mark comics with altered foreign keys for update."""
    if not fix_comic_pks:
        return
    comic_model: type[Comic] = apps.get_model(app_label="codex", model_name="comic")  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
    outdated_comics: BaseManager[Comic] = comic_model.objects.filter(
        pk__in=fix_comic_pks
    ).only(  # type: ignore[reportAssignmentType]
        "stat", "updated_at"
    )
    if not outdated_comics:
        return

    update_comics = []
    now = Now()
    for comic in outdated_comics:
        stat_list = comic.stat
        if not stat_list:
            continue
        stat_list[8] = 0.0
        comic.stat = stat_list  # pyright: ignore[reportAttributeAccessIssue]
        comic.updated_at = now
        update_comics.append(comic)

    if update_comics:
        count = comic_model.objects.bulk_update(
            update_comics, fields=["stat", "updated_at"]
        )
        log.info(f"Marked {count} comics with bad relations for update by poller.")


def fix_foreign_keys(log):
    """Foreign Key Check."""
    try:
        sql = _PRAGMA_TMPL % "foreign_key_check"
        results = _exec_sql(sql)
        if count := len(results):
            log.warning(f"Found {count} illegal foreign keys. Attempting fix...")
            log.debug(results)
        bad_fk_rels, bad_m2m_rows = _compile_foreign_key_results(results, log)
    except Exception:
        log.exception("Integrity: foreign_key_check")
        return
    try:
        fix_comic_pks = _null_bad_fk_rels(bad_fk_rels, log)
        fix_comic_pks |= _delete_bad_m2m_rows(bad_m2m_rows, log)
        if count := len(fix_comic_pks):
            _mark_comics_for_update(fix_comic_pks, log)
        else:
            log.success("Database passed foreign key check.")

    except Exception:
        log.exception("Could not mark comics with bad relations for update")


def _repair_extra_custom_cover_libraries(library_model, log):
    """Attempt to remove the bad ones, probably futile."""
    delete_libs = library_model.objects.filter(covers_only=True).exclude(
        path=CUSTOM_COVERS_DIR
    )
    count, _ = delete_libs.delete()
    if count:
        log.warning(
            f"Removed {count} duplicate custom cover libraries pointing to unused custom cover dirs."
        )


def cleanup_custom_cover_libraries(log):
    """Cleanup extra custom cover libraries."""
    try:
        try:
            library_model = apps.get_model("codex", "library")
        except LookupError:
            log.debug("Library model doesn't exist yet.")
            return
        if not library_model or not hasattr(library_model, "covers_only"):
            log.debug("Library model doesn't support custom cover library yet.")
            return
        _repair_extra_custom_cover_libraries(library_model, log)

        custom_cover_libraries = library_model.objects.filter(covers_only=True)
        count = custom_cover_libraries.count()
        if count > 1:
            count, _ = custom_cover_libraries.delete()
            if count:
                log.warning(
                    f"Removed all ({count}) custom cover libraries, Unable to determine valid one. Will recreate upon startup."
                )
    except Exception as exc:
        log.warning(f"Failed to check custom cover library for integrity - {exc}")


def _is_integrity_ok(results):
    return (
        results and len(results) == 1 and len(results[0]) == 1 and results[0][0] == "ok"
    )


def integrity_check(log, *, long: bool):
    """Run sqlite3 integrity check."""
    pragma = "integrity_check" if long else "quick_check"
    sql = _PRAGMA_TMPL % pragma
    log.debug(f"Running database '{sql}'...")
    results = _exec_sql(sql)

    if _is_integrity_ok(results):
        length = "" if long else "quick "
        log.success(f"Database passed {length}integrity check.")
    else:
        log.warning(f"Database '{sql}' returned results:")
        log.warning(results)
        log.warning(
            "See the README for database rebuild instructions if the above warning looks severe."
        )


def fts_rebuild():
    """FTS Rebuild."""
    sql = _FTS_INSERT_TMPL % "rebuild"
    _exec_sql(sql)


def fts_integrity_check(log):
    """Run sqlite3 fts integrity check."""
    results = []
    sql = _FTS_INSERT_TMPL % "integrity-check"
    success = False
    results = []
    try:
        results = _exec_sql(sql)
        if results:
            # I'm not sure if this raises or puts the error in the results.
            raise ValueError(results)  # noqa: TRY301
        log.success("Full Text Search Index passed integrity check.")
        success = True
    except Exception:
        log.exception("Full Text Search Index failed integrity check")
        log.debug(results)
    return success


class JanitorIntegrity(WorkerStatusMixin):
    """Integrity Check Mixin."""

    def __init__(self, *args, event, **kwargs):
        """Init self.log."""
        self.abort_event = event
        self.init_worker(*args, **kwargs)

    def foreign_key_check(self):
        """Foreign Key Check task."""
        status = JanitorDBFKIntegrityStatus()
        try:
            self.status_controller.start(status)
            with self.db_write_lock:
                fix_foreign_keys(self.log)
        finally:
            self.status_controller.finish(status)

    def integrity_check(self, *, long: bool):
        """Integrity check task."""
        subtitle = "" if long else "Quick"
        status = JanitorDBIntegrityStatus(subtitle=subtitle)
        try:
            self.status_controller.start(status)
            with self.db_write_lock:
                integrity_check(self.log, long=long)
        finally:
            self.status_controller.finish(status)

    def fts_rebuild(self):
        """FTS rebuild task."""
        status = JanitorDBFTSRebuildStatus()
        try:
            self.status_controller.start(status)
            with self.db_write_lock:
                fts_rebuild()
        finally:
            self.status_controller.finish(status)

    def fts_integrity_check(self):
        """FTS integrity check task."""
        status = JanitorDBFTSIntegrityStatus()
        try:
            self.status_controller.start(status)
            with self.db_write_lock:
                success = fts_integrity_check(self.log)
            if not success:
                self.librarian_queue.put(JanitorFTSRebuildTask())
        finally:
            self.status_controller.finish(status)
