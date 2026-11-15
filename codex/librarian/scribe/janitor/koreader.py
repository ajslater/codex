"""Backfill KOReader sync hashes."""

from typing import Final

from codex.librarian.scribe.janitor.status import JanitorKoreaderHashStatus
from codex.librarian.scribe.janitor.update import JanitorCodexUpdate
from codex.models import Comic
from codex.settings.db import koreader_sync_enabled

_BATCH_SIZE: Final = 500
_UPDATE_FIELDS: Final = ("koreader_hash", "koreader_name_hash")


class JanitorKoreaderHash(JanitorCodexUpdate):
    """Compute KOReader document hashes for comics imported without them."""

    def _koreader_hash_batch(self, last_pk: int) -> tuple[int, int]:
        """
        Hash one batch of comics after ``last_pk``.

        Returns ``(batch_size, last_pk)``. Walks by pk rather than
        re-querying the null set so a file that can't be read is skipped
        instead of retried forever; the next nightly run retries it.
        """
        comics = tuple(
            Comic.objects.filter(pk__gt=last_pk, koreader_hash__isnull=True)
            .order_by("pk")
            .only("pk", "path", *_UPDATE_FIELDS)[:_BATCH_SIZE]
        )
        if not comics:
            return 0, last_pk
        # Read the files outside the write lock.
        for comic in comics:
            comic.set_koreader_hashes()
        hashed = [comic for comic in comics if comic.koreader_hash]
        if hashed:
            with self.db_write_lock:
                Comic.objects.bulk_update(hashed, _UPDATE_FIELDS)
        return len(comics), comics[-1].pk

    def koreader_hash_backfill(self) -> None:
        """Hash every comic that has no KOReader hash, if the flag is on."""
        status = JanitorKoreaderHashStatus()
        try:
            # Finish the status even when off: the nightly run marks it
            # pending along with every other janitor job.
            if not koreader_sync_enabled():
                self.log.debug("KOReader Sync is off, not hashing comics.")
                return
            status.total = Comic.objects.filter(koreader_hash__isnull=True).count()
            self.status_controller.start(status)
            last_pk = 0
            while not self.abort_event.is_set():
                count, last_pk = self._koreader_hash_batch(last_pk)
                if not count:
                    break
                status.increment_complete(count)
                self.status_controller.update(status)
            level = "INFO" if status.total else "DEBUG"
            self.log.log(level, f"Hashed {status.complete or 0} comics for KOReader.")
        finally:
            self.status_controller.finish(status)
