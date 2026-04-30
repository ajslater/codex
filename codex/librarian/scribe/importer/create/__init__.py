"""
Create all missing comic many to many objects for an import.

So we may safely create the comics next.
"""

from codex.librarian.covers.status import CreateCoversStatus
from codex.librarian.covers.tasks import CoverCreateTask
from codex.librarian.scribe.importer.create.foreign_keys import (
    CreateForeignKeysCreateUpdateImporter,
)


class CreateForeignKeysImporter(CreateForeignKeysCreateUpdateImporter):
    """Methods for creating foreign keys."""

    def _update_pending_cover_create_total(self) -> None:
        """
        Refresh the pre-registered ``CreateCoversStatus`` total.

        ``update_comics`` and ``create_comics`` each stash their pks
        on ``self.cover_create_pks`` as they decide how many covers
        will be regenerated. Writing the running set size to the
        pre-registered (preactive) row gives the UI an accurate
        "queued, N covers" hint before the cover thread picks up the
        coalesced task and replaces the total via its own ``start()``.
        """
        status = CreateCoversStatus(total=len(self.cover_create_pks))
        self.status_controller.update(status)

    def _submit_coalesced_cover_task(self) -> None:
        """
        Submit one ``CoverCreateTask`` for both newly-created and updated comics.

        Both ``create_comics`` and ``update_comics`` populate
        ``self.cover_create_pks`` instead of submitting their own task.
        Combining them into a single submission means the cover thread
        runs one ``CreateCoversStatus`` start/finish per chunk; two
        back-to-back submissions would each start and finish their own
        status, blinking the row in and out of the active list as the
        cover thread switches tasks.

        If no pks accumulated (no created or updated comics in this
        chunk), explicitly clear the pre-registered ``CreateCoversStatus``
        so the row doesn't sit "queued" in the UI for the rest of the
        import.
        """
        if self.cover_create_pks:
            self.librarian_queue.put(
                CoverCreateTask(pks=tuple(self.cover_create_pks), custom=False)
            )
            self.cover_create_pks.clear()
        else:
            self.status_controller.finish_many((CreateCoversStatus,))

    def create_and_update(self) -> None:
        """
        Create and update FKs, covers and comics.

        The previous version wrapped the body in ``transaction.atomic``
        to coalesce the ~2000+ ``bulk_create`` / ``bulk_update`` commits
        this phase generates into a single fsync. That coalescing was a
        no-op in practice with the current ``importer_pragmas``
        (``synchronous=NORMAL`` + ``wal_autocheckpoint=0``) — every
        commit is a WAL frame append with no fsync until the post-
        import ``wal_checkpoint(TRUNCATE)`` — and it had a real
        downside: ``status_controller.start`` / ``update`` / ``finish``
        writes lived in the same transaction, so readers (admin status
        API, websocket-poller) couldn't see them until commit. By the
        time the multi-minute create-and-update transaction committed,
        ``finish()`` had already cleared each row, and the
        Create Tags / Update Tags / Create Comics / Update Comics
        spinners never appeared during the actual work.

        Without the wrapper each helper's bulk operation runs in
        Django's per-statement autocommit. Each ``start`` / ``update``
        / ``finish`` lands in its own transaction and is visible to
        readers immediately.

        Counts use ``+=`` so a chunked apply() loop can call
        ``create_and_update`` once per chunk and still report a
        correct total at finish.
        """
        if self.abort_event.is_set():
            return
        fk_count = self.create_all_fks()
        if self.abort_event.is_set():
            return
        fk_count += self.update_all_fks()
        self.counts.tags += fk_count
        if self.abort_event.is_set():
            return

        cover_count = self.create_custom_covers()
        if self.abort_event.is_set():
            return
        cover_count += self.update_custom_covers()
        self.counts.covers += cover_count

        if self.abort_event.is_set():
            return
        comic_count = self.update_comics()
        self._update_pending_cover_create_total()
        comic_count += self.create_comics()
        self._update_pending_cover_create_total()
        self.counts.comic += comic_count

        self._submit_coalesced_cover_task()
