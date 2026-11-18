"""Backfill KOReader sync hashes."""

from typing import Final

from codex.librarian.scribe.janitor.status import JanitorKoreaderHashStatus
from codex.librarian.scribe.janitor.tasks import JanitorKoreaderHashTask
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
        instead of retried forever; the next nightly run retries it. Its
        name hash, which needs no file, is saved all the same.
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
        with self.db_write_lock:
            Comic.objects.bulk_update(comics, _UPDATE_FIELDS)
        return len(comics), comics[-1].pk

    def koreader_hash_backfill(
        self, task: JanitorKoreaderHashTask | None = None
    ) -> None:
        """
        Hash a batch of comics that have no KOReader hash, if the flag is on.

        One batch per task, re-queued while rows remain: the scribe runs one
        task at a time, and imports and tag writes queued meanwhile rank
        ahead of the next batch instead of waiting out the whole library.
        The abort event is shared with every scribe job, so it is cleared
        on the way in and out.
        """
        task = task or JanitorKoreaderHashTask()
        self.abort_event.clear()
        status = JanitorKoreaderHashStatus()
        requeued = False
        try:
            # Finish the status even when off: the nightly run marks it
            # pending along with every other janitor job.
            if not koreader_sync_enabled():
                self.log.debug("KOReader Sync is off, not hashing comics.")
                return
            remaining = Comic.objects.filter(
                pk__gt=task.last_pk, koreader_hash__isnull=True
            ).count()
            status.total = task.done + remaining
            status.complete = task.done
            self.status_controller.start(status)
            count, last_pk = self._koreader_hash_batch(task.last_pk)
            done = task.done + count
            if count >= _BATCH_SIZE and not self.abort_event.is_set():
                status.complete = done
                self.status_controller.update(status)
                self.librarian_queue.put(
                    JanitorKoreaderHashTask(last_pk=last_pk, done=done)
                )
                requeued = True
                return
            level = "INFO" if done else "DEBUG"
            self.log.log(level, f"Hashed {done} comics for KOReader.")
        finally:
            if not requeued:
                self.status_controller.finish(status)
            self.abort_event.clear()
