"""Query missing foreign keys."""

from codex.librarian.importer.importer.const import (
    CREATE_FKS,
    DELETE_M2MS,
    QUERY_MODELS,
    UPDATE_COMICS,
    UPDATE_FKS,
)
from codex.librarian.importer.importer.query.links import QueryPruneLinks
from codex.librarian.importer.status import ImportStatusTypes

_STATII = (
    ImportStatusTypes.QUERY_MISSING_TAGS.value,
    ImportStatusTypes.QUERY_COMIC_UPDATES.value,
    ImportStatusTypes.QUERY_TAG_LINKS.value,
)


class QueryForeignKeysImporter(QueryPruneLinks):
    """Methods for querying missing fks."""

    def query_actions(self):
        """Get objects to create by querying existing objects for the proposed fks."""
        if QUERY_MODELS not in self.metadata:
            return
        self.metadata[UPDATE_COMICS] = {}
        self.metadata[CREATE_FKS] = {}
        self.metadata[UPDATE_FKS] = {}
        self.metadata[DELETE_M2MS] = {}
        self.log.debug(
            f"Querying existing foreign keys for comics in {self.library.path}"
        )
        try:
            self.query_all_missing_models()
            self.query_update_comics()
            self.query_prune_comic_links()
        finally:
            self.status_controller.finish_many(_STATII)
