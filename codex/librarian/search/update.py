"""Search Index update."""
from time import time

from humanize import naturaldelta
from whoosh.query import Every

from codex.librarian.search.remove import RemoveMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.version import VersionMixin
from codex.models import Comic, Library


class UpdateMixin(VersionMixin, RemoveMixin):
    """Search Index update methods."""

    _STATUS_UPDATE_START_TYPES = {
        SearchIndexStatusTypes.SEARCH_INDEX_UPDATE: {},
        SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE: {},
        SearchIndexStatusTypes.SEARCH_INDEX_REMOVE: {},
    }
    _STATUS_FINISH_TYPES = frozenset(
        (
            SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
            SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
            SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE,
            SearchIndexStatusTypes.SEARCH_INDEX_REMOVE,
        )
    )

    def _init_statuses(self, rebuild):
        """Initialize all statuses order before starting."""
        statuses = {}
        if rebuild:
            statuses[SearchIndexStatusTypes.SEARCH_INDEX_CLEAR] = {}
        statuses.update(self._STATUS_UPDATE_START_TYPES)
        self.status_controller.start_many(statuses)

    def _get_search_index_latest_updated_at(self, backend):
        """Get the date of the last updated item in the search index."""
        if not backend.setup_complete:
            backend.setup()
        backend.index = backend.index.refresh()

        with backend.index.searcher() as searcher:
            results = searcher.search(
                Every(), sortedby="updated_at", reverse=True, limit=1
            )
            if len(results):
                latest_doc = results[0]
                return latest_doc.get("updated_at")
        return None

    def _prepare_for_update(self, rebuild):
        """Rebuild or set up update."""
        backend = self.engine.get_backend()

        unified_index = self.engine.get_unified_index()
        index = unified_index.get_index(Comic)

        qs = Comic.objects.all()

        if not rebuild:
            last_updated_at = self._get_search_index_latest_updated_at(backend)
            # index.build_queryset() like in the haystack command does
            #   __gte not __gt
            if last_updated_at:
                qs = qs.filter(updated_at__gt=last_updated_at)
            else:
                last_updated_at = "the beginning of time"
            self.log.info(f"Updating search index since {last_updated_at}...")

        qs = qs.order_by("updated_at", "pk")

        return backend, index, qs

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

            self._init_statuses(rebuild)

            backend, index, qs = self._prepare_for_update(rebuild)

            # Clear
            if rebuild:
                self.log.info("Rebuilding search index...")
                backend.clear(models=[Comic], commit=True)
                self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)

            # Update
            try:
                backend.update(index, qs, commit=True)
            except Exception as exc:
                self.log.error(f"Update search index via backend: {exc}")
                self.log.exception(exc)

            # Finish
            if rebuild:
                self._set_search_index_version()
            else:
                self._remove_stale_records(backend)

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
