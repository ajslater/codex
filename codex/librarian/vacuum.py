"""Vacuum the database."""
from datetime import timedelta
from logging import getLogger

from django.db import connection
from django.utils import timezone

from codex.models import AdminFlag
from codex.settings.settings import DB_PATH


VACUUM_FREQ = timedelta(days=1)
LOG = getLogger(__name__)


def _is_vacuum_time(vacuum_flag):
    """Check if it's vacuum time."""
    if not vacuum_flag.on:
        LOG.debug("Database vacuum disabled.")
        return False

    elapsed = timezone.now() - vacuum_flag.updated_at
    if elapsed < VACUUM_FREQ:
        LOG.debug("Not time to vacuum the database yet.")
        return False

    return True


def vacuum_db():
    """Vacuum the database every day."""
    vacuum_flag = AdminFlag.objects.get(name=AdminFlag.ENABLE_AUTO_VACUUM)
    if not _is_vacuum_time(vacuum_flag):
        return

    old_size = DB_PATH.stat().st_size
    with connection.cursor() as cursor:
        cursor.execute("VACUUM")
    new_size = DB_PATH.stat().st_size
    saved = old_size - new_size
    vacuum_flag.save()  # update updated_at
    LOG.verbose(f"Vacuumed database. Saved {saved} bytes.")
