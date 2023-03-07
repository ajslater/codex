"""Search Index cleanup."""
from time import time
from typing import Optional

from haystack.constants import DJANGO_ID
from humanize import naturaldelta
from whoosh.query import Every, Or, Term

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.version import VersionMixin
from codex.models import Comic
from codex.search.backend import CodexSearchBackend


class RemoveMixin(VersionMixin):
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
                results = searcher.search(
                    Every(), limit=None, mask=mask, scored=False, sortedby=None
                )
                stale_doc_ids = results.docs()
            return stale_doc_ids
        finally:
            until = start + 1
            self.status_controller.finish(
                SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE, until=until
            )

    def _remove_stale_records(
        self, backend: Optional[CodexSearchBackend] = None  # type: ignore
    ):
        """Remove records not in the database from the index."""
        try:
            start_time = time()
            if not backend:
                backend: CodexSearchBackend = self.engine.get_backend()  # type: ignore
            if not backend.setup_complete:
                backend.setup(False)
            stale_doc_ids = self._get_stale_doc_ids(backend)
            num_doc_ids = len(stale_doc_ids)
            self.status_controller.start(
                SearchIndexStatusTypes.SEARCH_INDEX_REMOVE, num_doc_ids
            )
            backend.remove_batch_docnums(stale_doc_ids)

            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            cps = int(num_doc_ids / elapsed_time)
            self.log.info(
                f"Search engine removed {num_doc_ids} ghosts from the index"
                f" in {elapsed} at {cps} per second."
            )
        except Exception as exc:
            self.log.error("While removing stale records:")
            self.log.exception(exc)
        finally:
            self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)
