"""Clean up the database after moves or imports."""
import logging

from datetime import datetime

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.status_control import StatusControl
from codex.models import (
    Character,
    Credit,
    CreditPerson,
    CreditRole,
    Folder,
    Genre,
    Imprint,
    Location,
    Publisher,
    Series,
    SeriesGroup,
    StoryArc,
    Tag,
    Team,
    Volume,
)
from codex.settings.logging import get_logger


COMIC_FK_CLASSES = (
    Volume,
    Series,
    Imprint,
    Publisher,
    Folder,
    Credit,
    Tag,
    Team,
    Character,
    Location,
    SeriesGroup,
    StoryArc,
    Genre,
)
CREDIT_FK_CLASSES = (CreditRole, CreditPerson)
TOTAL_CLASSES = len(COMIC_FK_CLASSES) + len(CREDIT_FK_CLASSES)
LOG = get_logger(__name__)


def _bulk_cleanup_fks(classes, field_name, status_count):
    """Remove foreign keys that aren't used anymore."""
    since = datetime.now()
    for cls in classes:
        filter_dict = {f"{field_name}__isnull": True}
        query = cls.objects.filter(**filter_dict)
        count = query.count()
        query.delete()
        if count:
            LOG.info(f"Deleted {count} orphan {cls.__name__}s")
        status_count += 1
        since = StatusControl.update(
            JanitorStatusTypes.CLEANUP_FK,
            status_count,
            TOTAL_CLASSES,
            name=cls.__name__,
            since=since,
        )
    return status_count


def cleanup_fks():
    """Clean up unused foreign keys."""
    try:
        StatusControl.start(JanitorStatusTypes.CLEANUP_FK, TOTAL_CLASSES)
        LOG.debug("Cleaning up unused foreign keys...")
        status_count = 0
        status_count += _bulk_cleanup_fks(COMIC_FK_CLASSES, "comic", status_count)
        status_count += _bulk_cleanup_fks(CREDIT_FK_CLASSES, "credit", status_count)
        if status_count:
            level = logging.INFO
        else:
            level = logging.DEBUG
        LOG.log(level, f"Cleaned up {status_count} unused foreign keys.")
    finally:
        StatusControl.finish(JanitorStatusTypes.CLEANUP_FK)
