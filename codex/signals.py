"""Signal actions."""

from logging import getLogger

from django.db.backends.signals import connection_created


LOG = getLogger(__name__)


def activate_wal_journal(sender, connection, **kwargs):
    """Enable sqlite WAL journal."""
    if connection.vendor == "sqlite":
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=wal;")
        LOG.debug("sqlite journal_mode=wal")


connection_created.connect(activate_wal_journal)
