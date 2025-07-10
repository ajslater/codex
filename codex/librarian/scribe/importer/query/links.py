"""Prune link actions."""

from codex.librarian.scribe.importer.const import (
    LINK_FKS,
    LINK_M2MS,
)
from codex.librarian.scribe.importer.query.links_m2m import QueryPruneLinksM2M
from codex.librarian.scribe.importer.statii.query import ImporterQueryTagLinksStatus


class QueryPruneLinks(QueryPruneLinksM2M):
    """Prune link actions."""

    def query_prune_comic_links(self):
        """Prune links that don't need updating."""
        total_query_ops = self.sum_path_ops(LINK_FKS) + self.sum_path_ops(LINK_M2MS)
        status = ImporterQueryTagLinksStatus(0, total_query_ops)
        try:
            if not total_query_ops:
                return
            self.status_controller.start(status)
            if self.abort_event.is_set():
                return
            self.query_prune_comic_fk_links(status)
            if self.abort_event.is_set():
                return
            self.query_prune_comic_m2m_links(status)
        finally:
            self.status_controller.finish(status)
