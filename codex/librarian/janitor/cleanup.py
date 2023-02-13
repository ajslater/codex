"""Clean up the database after moves or imports."""
from datetime import datetime

from django.contrib.sessions.models import Session
from django.utils.timezone import now

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
TOTAL_CLASSES = len(DELETE_COMIC_FKS) + len(DELETE_CREDIT_FKS)
DELAY = 3
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
        LOG.verbose("Cleaning up unused foreign keys...")
        status_count = 0
        status_count = _bulk_cleanup_fks(DELETE_COMIC_FKS, "comic", status_count)
        _bulk_cleanup_fks(DELETE_CREDIT_FKS, "credit", status_count)
        LOG.verbose("Done cleaning up unused foreign keys.")
    finally:
        StatusControl.finish(JanitorStatusTypes.CLEANUP_FK)


def cleanup_sessions():
    """Delete corrupt sessions."""
    # start = now()
    StatusControl.start(JanitorStatusTypes.CLEANUP_SESSIONS)
    count, _ = Session.objects.filter(expire_date__lt=now()).delete()
    if count:
        LOG.info(f"Deleted {count} expired sessions.")

    bad_session_keys = set()
    for encoded_session in Session.objects.all():
        session = encoded_session.get_decoded()
        if not session:
            bad_session_keys.add(encoded_session.session_key)

    if not bad_session_keys:
        return

    bad_sessions = Session.objects.filter(session_key__in=bad_session_keys)
    count, _ = bad_sessions.delete()
    LOG.info(f"Deleted {count} corrupt sessions.")
    # elapsed = now() - start
    # delay = max(0, DELAY - elapsed.total_seconds())
    StatusControl.finish(JanitorStatusTypes.CLEANUP_SESSIONS)
