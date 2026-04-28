"""Bulk update m2m fields."""

from django.db import transaction

from codex.librarian.scribe.importer.link.many_to_many import LinkManyToManyImporter


class LinkComicsImporter(LinkManyToManyImporter):
    """Link comics methods."""

    def link(self) -> None:
        """
        Link tags and covers.

        Wrapped in ``transaction.atomic`` for the same reason as
        ``create_and_update``: coalesces the per-M2M-field
        ``bulk_create`` commits (one per linked relation) into a
        single fsync.
        """
        with transaction.atomic():
            self.counts.link += self.link_comic_m2m_fields()
            if self.abort_event.is_set():
                return
            if count := self.link_custom_covers():
                self.counts.link_covers += count
