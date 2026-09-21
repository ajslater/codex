"""Really delete rows whose retention window has expired."""

from datetime import timedelta
from typing import Final

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.scribe.importer.delete.collect import (
    init_comic_collection_map,
    populate_comic_collection_map,
)
from codex.librarian.scribe.janitor.cleanup import JanitorCleanup
from codex.librarian.scribe.janitor.status import JanitorReapPendingDeletesStatus
from codex.librarian.scribe.timestamp_update import TimestampUpdater
from codex.models import Comic, Folder, Library
from codex.settings import IMPORTER_LINK_FK_BATCH_SIZE

#: How long a row that vanished from disk is kept before it is really
#: deleted. A safety delay before an irreversible action, not a tuning
#: knob -- the same shape as the telemeter's opt-out window, which is
#: documented to admins in prose while still not being configurable.
#: The effective window is this plus the time to the next nightly run.
_PENDING_DELETE_WINDOW: Final = timedelta(hours=24)


class JanitorReap(JanitorCleanup):
    """Reap expired pending deletes."""

    def _reapable_folder_pks(self, cutoff) -> list[int]:
        """
        Expired folders that hold nothing live.

        A folder delete cascades to its comics through
        ``Comic.parent_folder`` and to sub-folders through
        ``Folder.parent_folder``, so reaping a stamped ancestor would
        take live descendants with it. Anything still live below it
        means the subtree is not really gone.
        """
        # ``Exists`` rather than ``exclude(comic__missing_since__isnull
        # =True)``: on a LEFT OUTER JOIN a folder with no comics at all
        # is NULL-extended, so the join form reads its absent comic as a
        # live one and refuses to reap the folder forever.
        live_comics = Comic.objects.filter(
            Q(parent_folder_id=OuterRef("pk")) | Q(folders=OuterRef("pk")),
            missing_since__isnull=True,
        )
        live_subfolders = Folder.objects.filter(
            parent_folder_id=OuterRef("pk"), missing_since__isnull=True
        )
        return list(
            Folder.objects.filter(missing_since__lt=cutoff)
            .filter(~Exists(live_comics), ~Exists(live_subfolders))
            .values_list("pk", flat=True)
        )

    def _reap_comics(self, cutoff, collection_map) -> tuple[int, set[int]]:
        """Delete expired comics in batches, gathering their collections first."""
        pks = list(
            Comic.objects.filter(missing_since__lt=cutoff).values_list("pk", flat=True)
        )
        reaped: set[int] = set()
        for start in range(0, len(pks), IMPORTER_LINK_FK_BATCH_SIZE):
            if self.abort_event.is_set():
                break
            batch = pks[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
            qs = Comic.objects.filter(pk__in=batch)
            # Before the delete: afterwards there is nothing to read the
            # collections off, and the browser's refresh probe reads a
            # collection's own updated_at, not its comics'.
            populate_comic_collection_map(qs, collection_map)
            reaped.update(batch)
            qs.delete()
        return len(reaped), reaped

    def _reap_folders(self, cutoff) -> int:
        """Delete expired empty folders in batches."""
        pks = self._reapable_folder_pks(cutoff)
        count = 0
        for start in range(0, len(pks), IMPORTER_LINK_FK_BATCH_SIZE):
            if self.abort_event.is_set():
                break
            batch = pks[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
            Folder.objects.filter(pk__in=batch).delete()
            count += len(batch)
        return count

    def _publish_reap(self, collection_map, comic_pks: set[int]) -> None:
        """
        Tell the rest of the app the rows are really gone.

        The janitor has no importer ``finish()`` to do this for it, and
        ``cleanup_fks`` notifying nothing is a gap rather than a
        precedent.
        """
        timestamp_updater = TimestampUpdater(
            self.log, self.librarian_queue, self.db_write_lock
        )
        now = timezone.now()
        for library in Library.objects.only("pk", "path"):
            timestamp_updater.update_library_collections(library, now, collection_map)
        if comic_pks:
            # The stamp deliberately left the covers in place so a
            # revived row would find its own; now that the row is really
            # gone they would leak until the orphan sweep.
            self.librarian_queue.put(
                CoverRemoveTask(frozenset(comic_pks), custom=False)
            )
        self.librarian_queue.put(LIBRARY_CHANGED_TASK)

    def reap_pending_deletes(self) -> None:
        """
        Really delete rows whose retention window has expired.

        Comics first, then folders: a folder is only reapable once
        nothing live remains under it, and reaping its comics is what
        can make that true.
        """
        self.abort_event.clear()
        status = JanitorReapPendingDeletesStatus(0)
        try:
            self.status_controller.start(status)
            cutoff = timezone.now() - _PENDING_DELETE_WINDOW
            collection_map = init_comic_collection_map()
            with self.db_write_lock:
                comics, comic_pks = self._reap_comics(cutoff, collection_map)
                folders = self._reap_folders(cutoff)
            total = comics + folders
            status.complete = total
            if total:
                reason = (
                    f"Reaped {comics} comics and {folders} folders"
                    f" missing for more than {_PENDING_DELETE_WINDOW}."
                )
                self.log.info(reason)
                self._publish_reap(collection_map, comic_pks)
            else:
                self.log.debug("No pending deletes were old enough to reap.")
        finally:
            if self.abort_event.is_set():
                self.log.info("Reap pending deletes task aborted early.")
            self.status_controller.finish(status)
