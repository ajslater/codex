"""Search Index update."""
from datetime import datetime
from multiprocessing import Pool, cpu_count
from time import time
from zoneinfo import ZoneInfo

from humanize import naturaldelta
from whoosh.query import Every

from codex.librarian.search.remove import RemoveMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.models import Comic, Library
from codex.search.backend import CodexSearchBackend


class UpdateMixin(RemoveMixin):
    """Search Index update methods."""

    _STATUS_UPDATE_START_TYPES = {
        SearchIndexStatusTypes.SEARCH_INDEX_UPDATE: {},
        SearchIndexStatusTypes.SEARCH_INDEX_REMOVE: {},
    }
    _STATUS_FINISH_TYPES = frozenset(
        (
            SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
            SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
            SearchIndexStatusTypes.SEARCH_INDEX_REMOVE,
        )
    )
    _MIN_UTC_DATE = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
    _MIN_BATCH_SIZE = 200
    # A larger batch size of might be slightly faster for very large
    # indexes and require less optimization later, but steady progress
    # beats are better UX.
    _MAX_BATCH_SIZE = 1000

    def _init_statuses(self, rebuild):
        """Initialize all statuses order before starting."""
        statuses = {}
        if rebuild:
            statuses[SearchIndexStatusTypes.SEARCH_INDEX_CLEAR] = {}
        statuses.update(self._STATUS_UPDATE_START_TYPES)
        self.status_controller.start_many(statuses)

    @classmethod
    def _get_latest_update_at_from_results(cls, results):
        """Can't use the search index to find the lowest date. Use python."""
        # SAD PANDA. :(
        index_latest_updated_at = cls._MIN_UTC_DATE
        for result in results:
            result_updated_at = result.get("updated_at")
            if result_updated_at > index_latest_updated_at:
                index_latest_updated_at = result_updated_at
        if index_latest_updated_at == cls._MIN_UTC_DATE:
            index_latest_updated_at = None
        return index_latest_updated_at

    def _get_search_index_latest_updated_at(self, backend):
        """Get the date of the last updated item in the search index."""
        if not backend.setup_complete:
            backend.setup(False)
        backend.index = backend.index.refresh()

        with backend.index.searcher() as searcher:
            # XXX idk why but sorting by 'updated_at' removes the latest and most valuable result
            results = searcher.search(Every(), reverse=True, scored=False)
            if results.scored_length():
                index_latest_updated_at = self._get_latest_update_at_from_results(
                    results
                )
            else:
                index_latest_updated_at = None

        return index_latest_updated_at

    def _get_queryset(self, backend, rebuild):
        """Rebuild or set up update."""
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
        return qs

    def _mp_update(self, backend, qs):
        # Init
        start_time = time()
        try:
            since = start_time
            num_comics = qs.count()
            self.status_controller.start(
                SearchIndexStatusTypes.SEARCH_INDEX_UPDATE, total=num_comics
            )
            num_cpus = cpu_count()
            batch_size = int(
                max(
                    self._MIN_BATCH_SIZE,
                    min(num_comics / num_cpus, self._MAX_BATCH_SIZE),
                )
            )
            num_procs = int(min(max(1, num_comics / batch_size), num_cpus))
            pool = Pool(num_procs)
            self.log.debug(
                f"Updating search index with {num_comics} comics,"
                f" using {num_procs} processes in batches of {batch_size}..."
            )

            # Run Loop
            start = 0
            end = start + batch_size
            results = []
            while start < num_comics:
                batch_qs = qs[start:end]
                args = (None, batch_qs)
                result = pool.apply_async(backend.update, args)
                results.append(result)

                start = end + 1
                end = start + batch_size
            pool.close()
            self.log.debug(f"{len(results)} search index update batches queued...")

            # Get results
            complete = 0
            for result in results:
                complete += result.get()
                since = self.status_controller.update(
                    SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
                    complete,
                    num_comics,
                    since=since,
                )
            pool.join()
            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            cps = int(num_comics / elapsed_time)
            self.log.info(
                f"Search engine updated {num_comics} comics"
                f" in {elapsed} at {cps} comics per second."
            )
        except Exception as exc:
            self.log.error(f"Update search index via backend: {exc}")
            self.log.exception(exc)
        finally:
            until = start_time + 1
            self.status_controller.finish(
                SearchIndexStatusTypes.SEARCH_INDEX_UPDATE, until=until
            )

    def _update_search_index(self, rebuild=False):
        """Update or Rebuild the search index."""
        start_time = time()
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

            backend: CodexSearchBackend = self.engine.get_backend()  # type: ignore
            qs = self._get_queryset(backend, rebuild)

            # Clear
            if rebuild:
                self.log.info("Rebuilding search index...")
                backend.clear(commit=True)
                self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
                self.log.info("Old search index cleared.")

            # Update
            backend.setup(False)
            self._mp_update(backend, qs)

            # Finish
            if rebuild:
                self._set_search_index_version()
            else:
                self._remove_stale_records(backend)

            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            self.log.info(f"Search index updated in {elapsed}.")
        except Exception as exc:
            self.log.error(f"Update search index: {exc}")
            self.log.exception(exc)
        finally:
            # Finishing these tasks inside the command process leads to a timing
            # misalignment. Finish it here works.
            until = start_time + 1
            self.status_controller.finish_many(self._STATUS_FINISH_TYPES, until=until)
