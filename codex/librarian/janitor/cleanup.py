"""Clean up the database after moves or imports."""

import logging
from pathlib import Path
from time import time
from types import MappingProxyType

from django.contrib.sessions.models import Session
from django.db.models.functions.datetime import Now

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.models import (
    AgeRating,
    Character,
    Contributor,
    ContributorPerson,
    ContributorRole,
    Country,
    Folder,
    Genre,
    Identifier,
    IdentifierType,
    Imprint,
    Language,
    Location,
    OriginalFormat,
    Publisher,
    ScanInfo,
    Series,
    SeriesGroup,
    StoryArc,
    StoryArcNumber,
    Tag,
    Tagger,
    Team,
    Volume,
)
from codex.models.bookmark import Bookmark
from codex.models.paths import CustomCover
from codex.status import Status
from codex.worker_base import WorkerBaseMixin

_COMIC_FK_CLASSES = (
    AgeRating,
    Country,
    Contributor,
    Character,
    Genre,
    Folder,
    Language,
    Location,
    Identifier,
    Imprint,
    OriginalFormat,
    Publisher,
    Series,
    SeriesGroup,
    ScanInfo,
    StoryArcNumber,
    Tagger,
    Tag,
    Team,
    Volume,
)
_CONTRIBUTOR_FK_CLASSES = (ContributorRole, ContributorPerson)
_STORY_ARC_NUMBER_FK_CLASSES = (StoryArc,)
_IDENTIFIER_FK_CLASSES = (IdentifierType,)
TOTAL_NUM_FK_CLASSES = (
    len(_COMIC_FK_CLASSES)
    + len(_CONTRIBUTOR_FK_CLASSES)
    + len(_STORY_ARC_NUMBER_FK_CLASSES)
    + len(_IDENTIFIER_FK_CLASSES)
)

CLEANUP_MAP = MappingProxyType(
    {
        "comic": _COMIC_FK_CLASSES,
        "contributor": _CONTRIBUTOR_FK_CLASSES,
        "storyarcnumber": _STORY_ARC_NUMBER_FK_CLASSES,
        "identifier": _IDENTIFIER_FK_CLASSES,
    }
)


class CleanupMixin(WorkerBaseMixin):
    """Cleanup methods for Janitor."""

    def _bulk_cleanup_fks(self, models, field_name, status):
        """Remove foreign keys that aren't used anymore."""
        for model in models:
            filter_dict = {f"{field_name}__isnull": True}
            qs = model.objects.filter(**filter_dict)
            count = qs.count()
            qs.delete()
            if count:
                self.log.info(f"Deleted {count} orphan {model.__name__}s")
            status.complete += count
            self.status_controller.update(status)

    def cleanup_fks(self):
        """Clean up unused foreign keys."""
        status = Status(JanitorStatusTypes.CLEANUP_FK, 0, TOTAL_NUM_FK_CLASSES)
        try:
            self.status_controller.start(status)
            self.log.debug("Cleaning up unused foreign keys...")
            for field_name, models in CLEANUP_MAP.items():
                self._bulk_cleanup_fks(models, field_name, status)
            level = logging.INFO if status.complete else logging.DEBUG
            self.log.log(level, f"Cleaned up {status.complete} unused foreign keys.")
        finally:
            self.status_controller.finish(status)

    def cleanup_custom_covers(self):
        """Clean up unused custom covers."""
        covers = CustomCover.objects.only("path")
        status = Status(JanitorStatusTypes.CLEANUP_COVERS, 0, covers.count())
        delete_pks = []
        try:
            self.status_controller.start(status)
            self.log.debug("Cleaning up db custom covers with no source images...")
            for cover in covers.iterator():
                if not Path(cover.path).exists():
                    delete_pks.append(cover.pk)
                status.increment_complete()
            delete_qs = CustomCover.objects.filter(pk__in=delete_pks)
            count = delete_qs.count()
            delete_qs.delete()
            level = logging.INFO if status.complete else logging.DEBUG
            self.log.log(level, f"Deleted {count} CustomCovers without source images.")
        finally:
            until = time() + 1
            self.status_controller.finish(status, until=until)

    def cleanup_sessions(self):
        """Delete corrupt sessions."""
        status = Status(JanitorStatusTypes.CLEANUP_SESSIONS)
        try:
            self.status_controller.start(status)
            count, _ = Session.objects.filter(expire_date__lt=Now()).delete()
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
            until = time() + 1
            self.status_controller.finish(status, until=until)

    def cleanup_orphan_bookmarks(self):
        """Delete bookmarks without users or sessions."""
        status = Status(JanitorStatusTypes.CLEANUP_BOOKMARKS)
        try:
            self.status_controller.start(status)
            orphan_bms = Bookmark.objects.filter(session=None, user=None)
            if count := orphan_bms.count():
                orphan_bms.delete()
                self.log.info(f"Deleted {count} orphan bookmarks.")
        finally:
            self.status_controller.finish(status)
