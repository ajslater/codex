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

    def _merge_search_index(self, optimize=False):
        """Optimize search index."""
        try:
            if optimize:
                name = "all segments"
            else:
                name = "small segments"

            self.status_controller.start(
                type=SearchIndexStatusTypes.SEARCH_INDEX_MERGE, name=name
            )
            start = time()

            old_num_segments = len(tuple(SEARCH_INDEX_PATH.glob("*.seg")))
            if self._is_index_optimized(old_num_segments):
                return

            # Optimize
            if optimize:
                method = "into one"
            else:
                method = "small segments"
            self.log.info(
                f"Search index found in {old_num_segments} segments,"
                f" merging {method}..."
            )
            backend: CodexSearchBackend = self.engine.get_backend()  # type: ignore
            if optimize:
                backend.optimize()
            else:
                backend.merge_small()

            # Finish
            new_num_segments = len(tuple(SEARCH_INDEX_PATH.glob("*.seg")))
            diff = old_num_segments - new_num_segments
            elapsed_time = time() - start
            elapsed = naturaldelta(elapsed_time)
            if diff:
                self.log.info(f"Merged {diff} search index segments in {elapsed}.")
            else:
                self.log.info("No small search index segments found.")
        except Exception as exc:
            self.log.error("Search index merge.")
            self.log.exception(exc)
        finally:
            self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_MERGE)
