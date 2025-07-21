"""Bulk update m2m fields."""

from codex.librarian.scribe.importer.link.many_to_many import LinkManyToManyImporter


class LinkComicsImporter(LinkManyToManyImporter):
    """Link comics methods."""

    def link(self):
        """Link tags and covers."""
        self.counts.link += self.link_comic_m2m_fields()
        if self.abort_event.is_set():
            return
        if count := self.link_custom_covers():
            self.counts.link_covers += count
