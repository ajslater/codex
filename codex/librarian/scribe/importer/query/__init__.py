"""Query missing foreign keys."""

from codex.librarian.scribe.importer.const import (
    CREATE_FKS,
    DELETE_M2MS,
    FTS_EXISTING_M2MS,
    QUERY_MODELS,
    UPDATE_COMICS,
    UPDATE_FKS,
)
from codex.librarian.scribe.importer.query.links import QueryPruneLinks
from codex.librarian.scribe.importer.statii.query import QUERY_STATII


class QueryForeignKeysImporter(QueryPruneLinks):
    """Methods for querying missing fks."""

    def query(self):
        """Get objects to create by querying existing objects for the proposed fks."""
        if QUERY_MODELS not in self.metadata:
            return
        self.metadata[UPDATE_COMICS] = {}
        self.metadata[CREATE_FKS] = {}
        self.metadata[UPDATE_FKS] = {}
        self.metadata[DELETE_M2MS] = {}
        self.metadata[FTS_EXISTING_M2MS] = {}
        self.log.debug(
            f"Querying existing foreign keys for comics in {self.library.path}"
        )
        try:
            if self.abort_event.is_set():
                return
            self.query_all_missing_models()
            if self.abort_event.is_set():
                return
            self.query_update_comics()
            if self.abort_event.is_set():
                return
            self.query_prune_comic_links()
            if self.abort_event.is_set():
                return
            self.query_missing_custom_covers()
        finally:
            self.status_controller.finish_many(QUERY_STATII)
