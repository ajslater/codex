"""Prune link actions."""

from codex.librarian.importer.importer.const import (
    LINK_FKS,
    LINK_M2MS,
)
from codex.librarian.importer.importer.query.links_m2m import QueryPruneLinksM2M
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.status import Status


class QueryPruneLinks(QueryPruneLinksM2M):
    """Prune link actions."""

    def query_prune_comic_links(self):
        """Prune links that don't need updating."""
        total_query_ops = self.sum_path_ops(LINK_FKS) + self.sum_path_ops(LINK_M2MS)
        status = Status(ImportStatusTypes.QUERY_TAG_LINKS, 0, total_query_ops)
        try:
            if not total_query_ops:
                return
            self.status_controller.start(status)
            self._query_prune_comic_fk_links(status)
            self._query_prune_comic_m2m_links(status)
        finally:
            self.status_controller.finish(status)
