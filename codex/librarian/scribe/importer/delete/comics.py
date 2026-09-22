"""Delete comics methods."""

from django.db.models.functions import Now

from codex.librarian.scribe.importer.delete.collect import (
    init_comic_collection_map,
    populate_comic_collection_map,
)
from codex.librarian.scribe.importer.delete.covers import DeletedCoversImporter
from codex.librarian.scribe.importer.delete.existence import confirm_deleted
from codex.librarian.scribe.importer.statii.delete import ImporterRemoveComicsStatus
from codex.models import Comic
from codex.settings import IMPORTER_LINK_FK_BATCH_SIZE

# A delete this large, and this much of the library, reads like a vanished
# mount rather than a user tidying up. The floor keeps small libraries from
# tripping it whenever a couple of comics are removed.
_MASS_DELETE_FLOOR = 50
_MASS_DELETE_FRACTION = 0.5


class DeletedComicsImporter(DeletedCoversImporter):
    """Delete comics methods."""

    _init_deleted_comic_collections = staticmethod(init_comic_collection_map)
    _populate_deleted_comic_collections = staticmethod(populate_comic_collection_map)

    def _warn_on_mass_delete(self, num_deleted: int) -> None:
        """
        Flag a delete large enough to look like the library vanished.

        An unmounted volume or dropped network share makes every path read
        as missing, which the existence backstop cannot tell from a real
        mass deletion. Nothing is blocked here — this only leaves a
        breadcrumb in the log for a user asking where their comics went.
        """
        if num_deleted < _MASS_DELETE_FLOOR:
            return
        total = Comic.objects.filter(library=self.library).count()
        if total and num_deleted >= total * _MASS_DELETE_FRACTION:
            reason = (
                f"Deleting {num_deleted} of {total} comics in"
                f" {self.library.path}. If that library lives on a network"
                f" share or removable volume, check that it is still mounted."
            )
            self.log.warning(reason)

    def _stamp_missing(self, model, batch_paths) -> int:
        """
        Keep a vanished row and record when it went missing.

        Runs only under ``soft_delete`` and only after the probes above,
        which is what makes it safe without any "do not stamp withheld
        paths" logic of its own. ``_withhold_unreadable`` already removed
        unreadable paths from the diff before the task was built,
        ``confirm_deleted`` returns only the ``gone`` bucket, and
        ``_confirm_cascade`` already dropped every folder above an extant
        comic.

        Never ``.save()``: ``WatchedPath.presave`` stats the path, which
        raises ``FileNotFoundError`` for exactly these rows.

        ``updated_at`` is written explicitly because ``auto_now`` does
        not fire on a queryset ``.update()``.

        ``missing_since__isnull=True`` is correctness, not an
        optimisation. A stamped row stays in the poller's reference
        snapshot, so the same vanished paths are re-emitted as deletes on
        every poll for the whole window; without the guard each poll
        rewrites the clock and the reaper never reaps anything. (The
        re-emission itself is also suppressed, in the snapshot diff.)
        """
        return model.objects.filter(
            library=self.library, path__in=batch_paths, missing_since__isnull=True
        ).update(missing_since=Now(), updated_at=Now())

    def bulk_comics_deleted(self, **kwargs) -> tuple[int, dict]:
        """Bulk delete comics found missing from the filesystem."""
        count = 0
        deleted_comic_collections = self._init_deleted_comic_collections()
        status = ImporterRemoveComicsStatus(0, len(self.task.files_deleted))
        try:
            if not self.task.files_deleted:
                return count, deleted_comic_collections
            self.status_controller.start(status)
            # Batch path__in to stay under SQLite's variable limit.
            paths = confirm_deleted(self.task.files_deleted, self.log, "comics")
            self.task.files_deleted = frozenset()
            if not paths:
                return count, deleted_comic_collections
            self._warn_on_mass_delete(len(paths))
            delete_comic_pks: set[int] = set()
            missing_count = 0
            for start in range(0, len(paths), IMPORTER_LINK_FK_BATCH_SIZE):
                if self.abort_event.is_set():
                    break
                batch_paths = paths[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
                delete_qs = Comic.objects.filter(
                    library=self.library, path__in=batch_paths
                )
                self._populate_deleted_comic_collections(
                    delete_qs, deleted_comic_collections
                )
                if self.task.soft_delete:
                    missing_count += self._stamp_missing(Comic, batch_paths)
                    continue
                delete_comic_pks.update(delete_qs.values_list("pk", flat=True))
                delete_qs.delete()

            if self.task.soft_delete:
                self.counts.comics_missing += missing_count
                # Covers are keyed on pk alone, so a revived row finds
                # its cover exactly where it left it -- a free win from
                # reusing the row. The reaper removes them when the
                # window really expires.
                return 0, deleted_comic_collections

            count = len(delete_comic_pks)
            self.remove_covers(delete_comic_pks, custom=False)
        finally:
            self.status_controller.finish(status)
        return count, deleted_comic_collections
