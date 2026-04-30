"""Bulk update m2m fields."""

from codex.librarian.scribe.importer.link.many_to_many import LinkManyToManyImporter


class LinkComicsImporter(LinkManyToManyImporter):
    """Link comics methods."""

    def link(self) -> None:
        """
        Link tags and covers.

        The previous version wrapped the body in ``transaction.atomic``
        to coalesce the per-M2M-field ``bulk_create`` commits into a
        single fsync. That coalescing was a no-op in practice with the
        current ``importer_pragmas`` (``synchronous=NORMAL`` +
        ``wal_autocheckpoint=0``) — every commit is a WAL frame append
        with no fsync until the post-import ``wal_checkpoint(TRUNCATE)``
        — and it had a real downside: ``status_controller.start`` /
        ``update`` / ``finish`` writes (the rows the admin status API
        and websocket-poller read) lived in the same transaction, so
        readers couldn't see them until commit. By the time a multi-
        minute link transaction committed, ``finish()`` had already
        cleared the row, and the spinner never appeared during the
        actual link work — even though the python log statements showed
        progress the whole time.

        Without the wrapper each helper's bulk operation runs in
        Django's per-statement autocommit. Each ``start`` / ``update``
        / ``finish`` lands in its own transaction and is visible to
        readers immediately.
        """
        self.counts.link += self.link_comic_m2m_fields()
        if self.abort_event.is_set():
            return
        if count := self.link_custom_covers():
            self.counts.link_covers += count
