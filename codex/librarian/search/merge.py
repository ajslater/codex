"""Search Index Merging for Read Optimization."""
from time import time

from humanize import naturaldelta

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.version import VersionMixin
from codex.search.backend import CodexSearchBackend
from codex.settings.settings import SEARCH_INDEX_PATH


class MergeMixin(VersionMixin):
    """Search Index Merge Methods."""

    def _is_index_optimized(self, num_segments):
        """Is the index already in one segment."""
        if num_segments <= 1:
            self.log.info("Search index already optimized.")
            return True
        return False


    def _merge_search_index(self, optimize=False, force=False):
        """Optimize search index."""
        try:
            if optimize:
                name = "all segments"
            else:
                name = "small segments"

            self.status_controller.start(
                type=SearchIndexStatusTypes.SEARCH_INDEX_MERGE, name=name
            )
            self.log.debug("Optimizing search index...")
            start = time()

            num_segments = len(tuple(SEARCH_INDEX_PATH.glob("*.seg")))
            if self._is_index_optimized(num_segments):
                return

            # Optimize
            if optimize:
                method = "into one"
            else:
                method = "small segments"
            self.log.info(
                f"Search index found in {num_segments} segments, merging {method}..."
            )
            backend: CodexSearchBackend = self.engine.get_backend()  # type: ignore
            if optimize:
                backend.optimize()
            else:
                backend.merge_small()

            # Finish
            elapsed_time = time() - start
            elapsed = naturaldelta(elapsed_time)
            num_docs = backend.index.doc_count()
            cps = int(num_docs / elapsed_time)
            self.log.info(
                f"Merged search index in {elapsed} at {cps} comics per second."
            )
        except Exception as exc:
            self.log.error("Search index merge.")
            self.log.exception(exc)
        finally:
            self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_MERGE)
