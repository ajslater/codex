"""Search Index cleanup."""
from time import time

from haystack.constants import DJANGO_ID
from whoosh.query import Every, Or, Term

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.models import Comic
from codex.worker_base import WorkerBaseMixin


class RemoveMixin(WorkerBaseMixin):
    """Search Index cleanup methods."""

    def _get_stale_doc_ids(self, backend):
        """Get the stale search index pks that are no longer in the database."""
        start = time()
        self.status_controller.start(SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE, 0)
        try:
            self.log.debug("Looking for stale records...")

            database_pks = (
                Comic.objects.all().order_by("pk").values_list("pk", flat=True)
            )

            mask = Or([Term(DJANGO_ID, str(pk)) for pk in database_pks])

            backend.index = backend.index.refresh()
            with backend.index.searcher() as searcher:
                results = searcher.search(Every(), limit=None, mask=mask)
                stale_doc_ids = results.docs()
            return stale_doc_ids
        finally:
            until = start + 1
            self.status_controller.finish(
                SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE, until=until
            )

    def _remove_stale_records(self, backend):
        """Remove records not in the database from the index."""
        try:
            if not backend.setup_complete:
                backend.setup()
            stale_doc_ids = self._get_stale_doc_ids(backend)
            backend.remove_batch(stale_doc_ids)
        except Exception as exc:
            self.log.error("While removing stale records:")
            self.log.exception(exc)
