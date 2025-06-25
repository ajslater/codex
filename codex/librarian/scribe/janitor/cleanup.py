"""Clean up the database after moves or imports."""

from pathlib import Path
from types import MappingProxyType

from django.contrib.sessions.models import Session
from django.db.models.functions.datetime import Now

from codex.librarian.scribe.janitor.latest_version import JanitorLatestVersion
from codex.librarian.scribe.janitor.status import JanitorStatusTypes
from codex.librarian.status import Status
from codex.models import (
    AgeRating,
    Character,
    Country,
    Credit,
    CreditPerson,
    CreditRole,
    Folder,
    Genre,
    Identifier,
    IdentifierSource,
    Imprint,
    Language,
    Location,
    OriginalFormat,
    Publisher,
    ScanInfo,
    Series,
    SeriesGroup,
    Story,
    StoryArc,
    StoryArcNumber,
    Tag,
    Tagger,
    Team,
    Universe,
    Volume,
)
from codex.models.bookmark import Bookmark
from codex.models.paths import CustomCover

_FK_MODELS = (
    Identifier,
    AgeRating,
    Country,
    CreditRole,
    CreditPerson,
    StoryArc,
    IdentifierSource,
    Credit,
    Character,
    Genre,
    Folder,
    Language,
    Location,
    Imprint,
    OriginalFormat,
    Publisher,
    Series,
    SeriesGroup,
    ScanInfo,
    StoryArcNumber,
    Story,
    Tagger,
    Tag,
    Team,
    Volume,
    Universe,
)
_TOTAL_NUM_FK_CLASSES = len(_FK_MODELS)


def _create_reverse_rel_map():
    rel_map = {}
    for model in _FK_MODELS:
        rev_rels = []
        filter_dict = {}
        for field in model._meta.get_fields():
            if not field.auto_created:
                continue
            if hasattr(field, "get_accessor_name") and (
                an := field.get_accessor_name()  # pyright: ignore[reportAttributeAccessIssue]
            ):
                rel = an
            elif field.name:
                rel = field.name
            else:
                continue
            if rel == "id":
                continue
            rel = rel.removesuffix("_set")
            rev_rels.append(rel)
            filter_dict[f"{rel}__isnull"] = True
        if filter_dict:
            rel_map[model] = filter_dict
    return MappingProxyType(rel_map)


_MODEL_REVERSE_EMPTY_FILTER_MAP = _create_reverse_rel_map()
_BOOKMARK_FILTER = dict.fromkeys(
    (f"{rel}__isnull" for rel in ("session", "user", "comic")), True
)


class JanitorCleanup(JanitorLatestVersion):
    """Cleanup methods for Janitor."""

    def _is_abort_cleanup(self) -> bool:
        if self.is_library_importing():
            self.log.warning("Not safe to cleanup unused tags.")
            return True
        return False

    def _bulk_del_model(self, model, filter_dict):
        qs = model.objects.filter(**filter_dict).distinct()
        count, _ = qs.delete()
        if count:
            self.log.info(f"Deleted {count} orphan {model.__name__}s")
        return count

    def _cleanup_fks_model(self, model, filter_dict, status):
        status.subtitle = model._meta.verbose_name_plural
        self.status_controller.update(status)
        count = self._bulk_del_model(model, filter_dict)
        status.complete += count
        self.status_controller.update(status)
        return count

    def _cleanup_fks_one_level(self, status):
        count = 0
        for model, filter_dict in _MODEL_REVERSE_EMPTY_FILTER_MAP.items():
            if self._is_abort_cleanup():
                return count
            count += self._cleanup_fks_model(model, filter_dict, status)
        return count

    def cleanup_fks(self):
        """Clean up unused foreign keys."""
        if self._is_abort_cleanup():
            return
        status = Status(JanitorStatusTypes.CLEANUP_TAGS, 0)
        try:
            self.status_controller.start(status)
            self.log.debug("Cleaning up orphan tags...")
            count = 1
            while count:
                # Keep churning until we stop finding orphan tags.
                count = 0
                if self._is_abort_cleanup():
                    break
                count = self._cleanup_fks_one_level(status)
            level = "INFO" if status.complete else "DEBUG"
            self.log.log(level, f"Cleaned up {status.complete} unused tags.")
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
            count, _ = delete_qs.delete()
            level = "INFO" if status.complete else "DEBUG"
            self.log.log(level, f"Deleted {count} CustomCovers without source images.")
        finally:
            self.status_controller.finish(status)

    def cleanup_sessions(self):
        """Delete corrupt sessions."""
        status = Status(JanitorStatusTypes.CLEANUP_SESSIONS)
        try:
            self.status_controller.start(status)
            qs = Session.objects.filter(expire_date__lt=Now())
            count, _ = qs.delete()
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
            self.status_controller.finish(status)

    def cleanup_orphan_bookmarks(self):
        """Delete bookmarks without users or sessions."""
        status = Status(JanitorStatusTypes.CLEANUP_BOOKMARKS)
        try:
            self.status_controller.start(status)
            orphan_bms = Bookmark.objects.filter(**_BOOKMARK_FILTER)
            count, _ = orphan_bms.delete()
            level = "INFO" if count else "DEBUG"
            self.log.log(level, f"Deleted {count} orphan bookmarks.")
        finally:
            self.status_controller.finish(status)
