"""Clean up the database after moves or imports."""
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


def _bulk_cleanup_fks(classes, field_name):
    """Remove foreign keys that aren't used anymore."""
    changed = False
    for cls in classes:
        filter_dict = {f"{field_name}__isnull": True}
        query = cls.objects.filter(**filter_dict)
        count = query.count()
        query.delete()
        if count:
            LOG.info(f"Deleted {count} orphan {cls.__name__}s")
            changed = True
    return changed


def cleanup_fks():
    """Clean up unused foreign keys."""
    LOG.verbose("Cleaning up unused foreign keys...")
    _bulk_cleanup_fks(DELETE_COMIC_FKS, "comic")
    _bulk_cleanup_fks(DELETE_CREDIT_FKS, "credit")
    LOG.verbose("Done cleaning up unused foreign keys.")
