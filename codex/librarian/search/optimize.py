"""Search Index Optimization."""
from time import time

from humanize import naturaldelta

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.version import VersionMixin
from codex.search.backend import CodexSearchBackend
from codex.settings.settings import SEARCH_INDEX_PATH


class OptimizeMixin(VersionMixin):
    """Search Index Optimization Methods."""

    # Docker constraints look like 3 comics per second.
    # Don't optimize if it might take longer than 20 minutes.
    # Can be much faster running native. 128 comics per second for instance.
    _OPTIMIZE_DOC_COUNT = 20 * 60 * 3

    def _is_index_optimized(self, num_segments):
        """Is the index already in one segment."""
        if num_segments <= 1:
            self.log.info("Search index already optimized.")
            return True
        return False

    def _is_too_big_to_optimize(self, backend):
        """Auto optimize limiter."""
        if not backend.setup_complete:
            backend.setup()
        backend.index = backend.index.refresh()
        num_docs = backend.index.doc_count()
        if num_docs > self._OPTIMIZE_DOC_COUNT:
            self.log.info(f"Search index > {self._OPTIMIZE_DOC_COUNT} comics.")
            return True
        return False

    def _optimize_search_index(self, force=False):
        """Optimize search index."""
        try:
            self.status_controller.start(
                type=SearchIndexStatusTypes.SEARCH_INDEX_OPTIMIZE
            )
            self.log.debug("Optimizing search index...")
            start = time()

            num_segments = len(tuple(SEARCH_INDEX_PATH.glob("*.seg")))
            if self._is_index_optimized(num_segments):
                return

            backend: CodexSearchBackend = self.engine.get_backend()  # type: ignore
            if self._is_too_big_to_optimize(backend) and not force:
                self.log.info("Not optimizing.")
                return

            # Optimize
            self.log.info(
                f"Search index found in {num_segments} segments, optmizing..."
            )
            backend.optimize()

            # Finish
            elapsed_time = time() - start
            elapsed = naturaldelta(elapsed_time)
            num_docs = backend.index.doc_count()
            cps = int(num_docs / elapsed_time)
            self.log.info(
                f"Optimized search index in {elapsed} at {cps} comics per second."
            )
        except Exception as exc:
            self.log.error("Search index optimize.")
            self.log.exception(exc)
        finally:
            self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_OPTIMIZE)
