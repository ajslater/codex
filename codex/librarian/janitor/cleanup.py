"""Clean up the database after moves or imports."""
import logging
from time import time

from django.contrib.sessions.models import Session
from django.utils.timezone import now

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.models import (
    Character,
    Creator,
    CreatorPerson,
    CreatorRole,
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
from codex.status import Status
from codex.worker_base import WorkerBaseMixin

_COMIC_FK_CLASSES = (
    Volume,
    Series,
    Imprint,
    Publisher,
    Folder,
    Creator,
    Tag,
    Team,
    Character,
    Location,
    SeriesGroup,
    StoryArc,
    Genre,
)
_CREATOR_FK_CLASSES = (CreatorRole, CreatorPerson)
TOTAL_NUM_FK_CLASSES = len(_COMIC_FK_CLASSES) + len(_CREATOR_FK_CLASSES)


class CleanupMixin(WorkerBaseMixin):
    """Cleanup methods for Janitor."""

    def _bulk_cleanup_fks(self, classes, field_name, status):
        """Remove foreign keys that aren't used anymore."""
        for cls in classes:
            filter_dict = {f"{field_name}__isnull": True}
            query = cls.objects.filter(**filter_dict)
            count = query.count()
            query.delete()
            if count:
                self.log.info(f"Deleted {count} orphan {cls.__name__}s")
            status.complete += 1
            self.status_controller.update(status)

    def cleanup_fks(self):
        """Clean up unused foreign keys."""
        status = Status(JanitorStatusTypes.CLEANUP_FK, 0, TOTAL_NUM_FK_CLASSES)
        try:
            self.status_controller.start(status)
            self.log.debug("Cleaning up unused foreign keys...")
            self._bulk_cleanup_fks(_COMIC_FK_CLASSES, "comic", status)
            self._bulk_cleanup_fks(_CREATOR_FK_CLASSES, "creator", status)
            level = logging.INFO if status.complete else logging.DEBUG
            self.log.log(level, f"Cleaned up {status.complete} unused foreign keys.")
        finally:
            self.status_controller.finish(status)

    def cleanup_sessions(self):
        """Delete corrupt sessions."""
        start = time()
        status = Status(JanitorStatusTypes.CLEANUP_SESSIONS)
        try:
            self.status_controller.start(status)
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
        finally:
            until = start + 2
            self.status_controller.finish(status, until=until)
