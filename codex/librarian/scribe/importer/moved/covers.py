"""Bulk import and move covers."""

from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.scribe.importer.const import (
    CLASS_CUSTOM_COVER_GROUP_MAP,
    CUSTOM_COVER_UPDATE_FIELDS,
    LINK_COVER_PKS,
)
from codex.librarian.scribe.importer.moved.comics import MovedComicsImporter
from codex.librarian.scribe.importer.statii.moved import ImporterMoveCoversStatus
from codex.models import CustomCover


class MovedCoversImporter(MovedComicsImporter):
    """Methods for moving comics and folders."""

    def _bulk_covers_moved_prepare(self, status):
        """Create an update map for bulk update."""
        covers = CustomCover.objects.filter(
            library=self.library, path__in=self.task.covers_moved.keys()
        ).only("pk", "path")

        if status:
            status.total = covers.count()

        moved_covers = []
        unlink_pks = set()
        for cover in covers.iterator():
            try:
                new_path = self.task.covers_moved[cover.path]
                cover.path = new_path
                new_path = Path(new_path)
                cover.updated_at = Now()
                cover.presave()
                moved_covers.append(cover)
                unlink_pks.add(cover.pk)
            except Exception:
                self.log.exception(f"moving {cover.path}")
        return moved_covers, unlink_pks

    def _bulk_covers_moved_unlink(self, unlink_pks):
        """Unlink moved covers because they could have moved between group dirs."""
        if not unlink_pks:
            return
        self.log.debug(f"Unlinking {len(unlink_pks)} moved custom covers.")
        for model in CLASS_CUSTOM_COVER_GROUP_MAP:
            groups = model.objects.filter(custom_cover__in=unlink_pks)
            unlink_groups = []
            for group in groups:
                group.custom_cover = None
                unlink_groups.append(group)
            if unlink_groups:
                model.objects.bulk_update(unlink_groups, ["custom_cover"])
                self.log.debug(
                    f"Unlinked {len(unlink_groups)} {model.__name__} moved custom covers."
                )

        self.remove_covers(unlink_pks, custom=True)

    def bulk_covers_moved(self, status=None):
        """Move covers."""
        num_covers_moved = len(self.task.covers_moved)
        status = ImporterMoveCoversStatus(None, num_covers_moved)
        try:
            if not num_covers_moved:
                return 0
            self.status_controller.start(status)

            moved_covers, unlink_pks = self._bulk_covers_moved_prepare(status)
            if LINK_COVER_PKS not in self.metadata:
                self.metadata[LINK_COVER_PKS] = set()
            self.metadata[LINK_COVER_PKS].update(unlink_pks)
            if moved_covers:
                CustomCover.objects.bulk_update(
                    moved_covers, CUSTOM_COVER_UPDATE_FIELDS
                )

            self._bulk_covers_moved_unlink(unlink_pks)

            count = len(moved_covers)
            level = "INFO" if count else "DEBUG"
            self.log.log(level, f"Moved {count} custom covers.")
        finally:
            self.status_controller.finish(status)
        return count
