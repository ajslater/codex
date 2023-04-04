"""Search Index Merging for Read Optimization."""
from pathlib import Path
from time import time
from typing import TYPE_CHECKING

from humanize import naturaldelta, naturalsize

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import SearchIndexRemoveStaleTask
from codex.librarian.search.version import VersionMixin
from codex.settings.settings import SEARCH_INDEX_PATH
from codex.status import Status

if TYPE_CHECKING:
    from codex.search.backend import CodexSearchBackend


class MergeMixin(VersionMixin):
    """Search Index Merge Methods."""

    def _is_index_optimized(self, num_segments):
        """Is the index already in one segment."""
        if num_segments <= 1:
            self.log.info("Search index already optimized.")
            return True
        return False

    @staticmethod
    def _get_segments_and_len():
        segments = SEARCH_INDEX_PATH.glob("*.seg")
        num_segments = len(tuple(segments))
        return segments, num_segments

    @staticmethod
    def _get_segments_size(segments):
        size = 0
        for segment in segments:
            size += Path(segment).stat().st_size
        return size

    def merge_search_index(self, optimize=False):
        """Optimize search index."""
        verb = "All" if optimize else "Small"
        name = f"Merge {verb} Segments"
        status = Status(SearchIndexStatusTypes.SEARCH_INDEX_MERGE, subtitle=name)
        try:
            statii = (
                status,
                Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE),
            )
            self.status_controller.start_many(statii)
            start = time()

            segments, old_num_segments = self._get_segments_and_len()
            if self._is_index_optimized(old_num_segments):
                return
            self.status_controller.start(status)
            old_size = self._get_segments_size(segments)
            # Optimize
            self.log.info(
                f"Search index found in {old_num_segments} segments,"
                f" merging {name}..."
            )
            backend: CodexSearchBackend = self.engine.get_backend()  # type: ignore
            if optimize:
                backend.optimize()
            else:
                backend.merge_small()

            # Finish
            segments, new_num_segments = self._get_segments_and_len()
            new_size = self._get_segments_size(segments)
            saved = naturalsize(old_size - new_size)
            num_segments_diff = old_num_segments - new_num_segments
            elapsed_time = time() - start
            elapsed = naturaldelta(elapsed_time)
            if num_segments_diff:
                self.log.info(
                    f"Merged {num_segments_diff} search index segments in {elapsed}."
                    f"Saved {saved}."
                )
            else:
                self.log.info("No small search index segments found.")
            self.librarian_queue.put(SearchIndexRemoveStaleTask())
        except Exception:
            self.log.exception("Search index merge.")
        finally:
            self.status_controller.finish(status)
