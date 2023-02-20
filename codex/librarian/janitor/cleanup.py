"""Clean up the database after moves or imports."""
import logging
from time import time

from django.contrib.sessions.models import Session
from django.utils.timezone import now

from codex.librarian.janitor.status import JanitorStatusTypes
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
from codex.worker_base import WorkerBaseMixin

_COMIC_FK_CLASSES = (
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
_CREDIT_FK_CLASSES = (CreditRole, CreditPerson)
TOTAL_NUM_FK_CLASSES = len(_COMIC_FK_CLASSES) + len(_CREDIT_FK_CLASSES)


class CleanupMixin(WorkerBaseMixin):
    """Cleanup methods for Janitor."""

    def _bulk_cleanup_fks(self, classes, field_name, status_count):
        """Remove foreign keys that aren't used anymore."""
        since = time()
        for cls in classes:
            filter_dict = {f"{field_name}__isnull": True}
            query = cls.objects.filter(**filter_dict)
            count = query.count()
            query.delete()
            if count:
                self.log.info(f"Deleted {count} orphan {cls.__name__}s")
            status_count += 1
            since = self.status_controller.update(
                JanitorStatusTypes.CLEANUP_FK,
                status_count,
                TOTAL_NUM_FK_CLASSES,
                name=cls.__name__,
                since=since,
            )
        return status_count

    def cleanup_fks(self):
        """Clean up unused foreign keys."""
        try:
            self.status_controller.start(
                JanitorStatusTypes.CLEANUP_FK, TOTAL_NUM_FK_CLASSES
            )
            self.log.debug("Cleaning up unused foreign keys...")
            status_count = 0
            status_count += self._bulk_cleanup_fks(
                _COMIC_FK_CLASSES, "comic", status_count
            )
            status_count += self._bulk_cleanup_fks(
                _CREDIT_FK_CLASSES, "credit", status_count
            )
            if status_count:
                level = logging.INFO
            else:
                level = logging.DEBUG
            self.log.log(level, f"Cleaned up {status_count} unused foreign keys.")
        finally:
            self.status_controller.finish(JanitorStatusTypes.CLEANUP_FK)

    def cleanup_sessions(self):
        """Delete corrupt sessions."""
        start = time()
        self.status_controller.start(JanitorStatusTypes.CLEANUP_SESSIONS)
        count, _ = Session.objects.filter(expire_date__lt=now()).delete()
        if count:
            self.log.info(f"Deleted {count} expired sessions.")

        bad_session_keys = set()
        for encoded_session in Session.objects.all():
            session = encoded_session.get_decoded()
            if not session:
                bad_session_keys.add(encoded_session.session_key)

        if bad_session_keys:
            bad_sessions = Session.objects.filter(session_key__in=bad_session_keys)
            count, _ = bad_sessions.delete()
            self.log.info(f"Deleted {count} corrupt sessions.")
        until = start + 2
        self.status_controller.finish(JanitorStatusTypes.CLEANUP_SESSIONS, until=until)
