"""Vacuum the database."""
from datetime import datetime, timedelta
from logging import getLogger

from django.db import connection

from codex.settings.settings import CACHE_PATH, DB_PATH


VACUUM_LOCK_PATH = CACHE_PATH / "db_vacuum.timestamp"
CACHE_EXPIRY = timedelta(days=1)
LOG = getLogger(__name__)


def is_vacuum_time():
    """Check if it's vacuum time."""
    if not VACUUM_LOCK_PATH.exists():
        return True

    mtime = VACUUM_LOCK_PATH.stat().st_mtime
    mtime = datetime.fromtimestamp(mtime)
    expiry_time = mtime + CACHE_EXPIRY

    if expiry_time < datetime.now():
        return True

    LOG.debug("Not time to vacuum yet")
    return False


def vacuum_db():
    """Vacuum the database every day."""
    if not is_vacuum_time():
        return

    old_size = DB_PATH.stat().st_size
    with connection.cursor() as cursor:
        cursor.execute("VACUUM")
    new_size = DB_PATH.stat().st_size
    saved = new_size - old_size
    VACUUM_LOCK_PATH.touch()
    LOG.info("Vacuumed database. Saved %s bytes", saved)
