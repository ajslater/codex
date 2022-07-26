"""Clean up the database after moves or imports."""
from codex.librarian.status import librarian_status_done, librarian_status_update
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


DELETE_COMIC_FKS = (
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
DELETE_CREDIT_FKS = (CreditRole, CreditPerson)
LOG = get_logger(__name__)
CLEANUP_FK_STATUS_KEYS = {"type": "Cleanup Foreign Keys"}
TOTAL_CLASSES = len(DELETE_COMIC_FKS) + len(DELETE_CREDIT_FKS)


def _bulk_cleanup_fks(classes, field_name, status_count):
    """Remove foreign keys that aren't used anymore."""
    for cls in classes:
        filter_dict = {f"{field_name}__isnull": True}
        query = cls.objects.filter(**filter_dict)
        count = query.count()
        query.delete()
        if count:
            LOG.info(f"Deleted {count} orphan {cls.__name__}s")
        status_count += 1
        librarian_status_update(CLEANUP_FK_STATUS_KEYS, status_count, TOTAL_CLASSES)
    return status_count


def cleanup_fks():
    """Clean up unused foreign keys."""
    librarian_status_update(CLEANUP_FK_STATUS_KEYS, 0, TOTAL_CLASSES)
    LOG.verbose("Cleaning up unused foreign keys...")
    status_count = 0
    status_count = _bulk_cleanup_fks(DELETE_COMIC_FKS, "comic", status_count)
    _bulk_cleanup_fks(DELETE_CREDIT_FKS, "credit", status_count)
    librarian_status_done([CLEANUP_FK_STATUS_KEYS])
    LOG.verbose("Done cleaning up unused foreign keys.")
