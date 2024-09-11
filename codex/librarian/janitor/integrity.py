"""Database integrity checks and remedies."""

import re

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models.functions import Now
from django.db.utils import OperationalError

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.logger.logging import get_logger
from codex.settings.settings import (
    CONFIG_PATH,
    DB_PATH,
)
from codex.status import Status
from codex.worker_base import WorkerBaseMixin

REPAIR_FLAG_PATH = CONFIG_PATH / "rebuild_db"
REBUILT_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".rebuilt")
BACKUP_DB_PATH = DB_PATH.parent / (DB_PATH.name + ".bak")
DUMP_LINE_MATCHER = re.compile("TRANSACTION|ROLLBACK|COMMIT")

LOG = get_logger(__name__)


def _foreign_key_check(log):
    """Get table and row ids from foreign_key_check."""
    connection = connections[DEFAULT_DB_ALIAS]
    connection.prepare_database()
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_key_check;")
        results = cursor.fetchall()

    illegal_rows = {}

    for row in results:
        table_name, rowid, _parent, _fkid = row
        if table_name not in illegal_rows:
            illegal_rows[table_name] = set()
        illegal_rows[table_name].add(rowid)

    if not illegal_rows:
        log.info("Database passed foreign key check.")

    return illegal_rows


def _delete_illegal_foreign_key_relations_in_table(table_name, ids, fix_comic_pks, log):
    """Delete illegal foreign keys for one table."""
    model_name = table_name.replace("_", "")
    model = apps.get_model(app_label="codex", model_name=model_name)
    count = len(ids)
    qs = model.objects.filter(id__in=ids)
    try:
        comic_ids = qs.values_list("comic_id", flat=True)
        fix_comic_pks |= set(comic_ids)
    except (OperationalError, AttributeError):
        log.exception("Add comic ids to fix list.")

    qs.delete()
    log.warn(f"Deleted {count} {table_name} rows that failed integrity check.")
    return count


def _delete_illegal_foreign_key_relations(illegal_rows, log):
    """Delete illegal foreign keys for all tables."""
    fix_comic_pks = set()
    count = 0
    for table_name, ids in illegal_rows.items():
        try:
            count += _delete_illegal_foreign_key_relations_in_table(
                table_name, ids, fix_comic_pks, log
            )
        except Exception as exc:
            log.warn(f"Could not delete bad foreign keys in table {table_name} - {exc}")
    if count:
        log.info(f"Removed {count} bad foreign key relations.")
    return fix_comic_pks


def _mark_comics_for_update(fix_comic_pks, log):
    """Mark comics with altered foreign keys for update."""
    if not fix_comic_pks:
        return
    comic_model = apps.get_model(app_label="codex", model_name="comic")
    outdated_comics = comic_model.objects.filter(pk__in=fix_comic_pks).only(
        "stat", "updated_at"
    )
    if not outdated_comics:
        return

    update_comics = []
    now = Now()
    for comic in outdated_comics:
        stat_list = comic.stat  # type: ignore
        if not stat_list:
            continue
        stat_list[8] = 0.0
        comic.stat = stat_list  # type: ignore
        comic.updated_at = now  # type: ignore
        update_comics.append(comic)

    if update_comics:
        count = comic_model.objects.bulk_update(
            update_comics, fields=["stat", "updated_at"]
        )
        log.info(f"Marked {count} comics with bad relations for update by poller.")


def fix_foreign_keys(log=None):
    """Foreign Key Check."""
    if not log:
        log = LOG
    try:
        illegal_rows = _foreign_key_check(log)
    except Exception:
        log.exception("Integrity: foreign_key_check")
        return
    fix_comic_pks = _delete_illegal_foreign_key_relations(illegal_rows, log)
    try:
        _mark_comics_for_update(fix_comic_pks, log)
    except Exception as exc:
        LOG.warning(f"Could not mark comics with bad relations for update: {exc}")


def _is_integrity_ok(results):
    return (
        results and len(results) == 1 and len(results[0]) == 1 and results[0][0] == "ok"
    )


def integrity_check(long=False, log=None):
    """Run sqlite3 integrity check."""
    pragma = "integrity_check" if long else "quick_check"
    connection = connections[DEFAULT_DB_ALIAS]
    connection.prepare_database()
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA {pragma};")
        results = cursor.fetchall()

    if not log:
        log = LOG

    if _is_integrity_ok(results):
        length = "thorough" if long else "quick"
        log.info(f"Database passed {length} integrity check.")
    else:
        log.error(
            "Database integrity compromised. See the README for database rebuild instructions."
        )
        log.error(results)


class IntegrityMixin(WorkerBaseMixin):
    """Integrity Check Mixin."""

    def foreign_key_check(self):
        """Foreign Key Check task."""
        status = Status(JanitorStatusTypes.INTEGRITY_FK)
        try:
            self.status_controller.start(status)
            fix_foreign_keys(self.log)
        finally:
            self.status_controller.finish(status)

    def integrity_check(self, long=False):
        """Integrity check task."""
        subtitle = "Thorough" if long else "Quick"
        status = Status(JanitorStatusTypes.INTEGRITY_CHECK, subtitle=subtitle)
        try:
            self.status_controller.start(status)
            integrity_check(long, self.log)
        finally:
            self.status_controller.finish(status)
