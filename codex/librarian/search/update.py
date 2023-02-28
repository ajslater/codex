"""Search Index update."""
from time import time

from humanize import naturaldelta
from whoosh.query import Every

from codex.librarian.search.remove import RemoveMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.version import VersionMixin
from codex.models import Comic, Library
from codex.settings.settings import SEARCH_INDEX_PATH


class UpdateMixin(VersionMixin, RemoveMixin):
    """Search Index update methods."""

    _STATUS_FINISH_TYPES = frozenset(
        (
            SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
            SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
            SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE,
            SearchIndexStatusTypes.SEARCH_INDEX_REMOVE,
        )
    )

    def _get_search_index_latest_updated_at(self, backend):
        if not backend.setup_complete:
            backend.setup()
        backend.index = backend.index.refresh()
        with backend.index.searcher() as searcher:
            results = searcher.search(
                Every(), sortedby="updated_at", reverse=True, limit=1
            )
            if not len(results):
                return None
            return results[0].get("updated_at")

    def _update_search_index(self, rebuild=False):
        """Update or Rebuild the search index."""
        start = time()
        try:
            any_update_in_progress = Library.objects.filter(
                update_in_progress=True
            ).exists()
            if any_update_in_progress:
                self.log.debug(
                    "Database update in progress, not updating search index yet."
                )
                return

            if not rebuild and not self._is_search_index_uuid_match():
                self.log.warning("Database does not match search index.")
                rebuild = True

            statuses = {}
            if rebuild:
                statuses[SearchIndexStatusTypes.SEARCH_INDEX_CLEAR] = {}
            statuses.update(
                {
                    SearchIndexStatusTypes.SEARCH_INDEX_UPDATE: {},
                    SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE: {},
                    SearchIndexStatusTypes.SEARCH_INDEX_REMOVE: {},
                }
            )
            self.status_controller.start_many(statuses)

            SEARCH_INDEX_PATH.mkdir(parents=True, exist_ok=True)

            backend = self.engine.get_backend()

            unified_index = self.engine.get_unified_index()
            index = unified_index.get_index(Comic)

            if rebuild:
                self.log.info("Rebuilding search index...")
                backend.clear(models=[Comic], commit=True)
                self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
                start_date = None
            else:
                start_date = self._get_search_index_latest_updated_at(backend)
                self.log.info(f"Updating search index since {start_date}...")

            qs = index.build_queryset(using=backend, start_date=start_date).order_by(
                "updated_at", "pk"
            )

            try:
                backend.update(index, qs, commit=True)
            except Exception as exc:
                self.log.error(f"Update search index via backend: {exc}")
                self.log.exception(exc)

            if rebuild:
                self._set_search_index_version()
            else:
                self._remove_stale_records(qs, backend, start_date)

            elapsed = naturaldelta(time() - start)
            self.log.info(f"Search index updated in {elapsed}.")
        except Exception as exc:
            self.log.error(f"Update search index: {exc}")
            self.log.exception(exc)
        finally:
            # Finishing these tasks inside the command process leads to a timing
            # misalignment. Finish it here works.
            until = start + 1
            self.status_controller.finish_many(self._STATUS_FINISH_TYPES, until=until)
