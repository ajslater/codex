"""Search Index update."""
from datetime import datetime
from multiprocessing import Pool, cpu_count
from time import time
from zoneinfo import ZoneInfo

from django.db import DatabaseError
from haystack.exceptions import SearchFieldError
from humanize import naturaldelta
from whoosh.query import Every

from codex.librarian.search.remove import RemoveMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.memory import get_mem_limit
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
    _MIN_BATCH_SIZE = 10
    # A larger batch size of might be slightly faster for very large
    # indexes and require less optimization later, but steady progress
    # beats are better UX.
    _MAX_BATCH_SIZE = 600
    _MAX_RETRIES = 10

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

        if rebuild:
            start_date = "the beginning of time"
        else:
            start_date = self._get_search_index_latest_updated_at(backend)
            qs = qs.filter(updated_at__gt=start_date)

        self.log.info(f"Updating search index since {start_date}...")

        return qs

    def _get_throttle_params(self, num_comics):
        """Get params based on memory and total number of comics."""
        num_cpus = cpu_count()
        mem_limit_gb = get_mem_limit("g")
        if mem_limit_gb >= 2:
            procs = num_cpus
        else:
            procs = max(num_cpus, 6)
        batch_size = int(
            max(
                self._MIN_BATCH_SIZE,
                min(num_comics / procs, self._MAX_BATCH_SIZE),
            )
        )
        procs_mem_limit = int(6 * mem_limit_gb)  # special case for very low mem env.
        num_procs = int(min(max(1, num_comics / batch_size), num_cpus, procs_mem_limit))
        self.log.debug(
            f"Updating search index: {num_comics=}"
            f" mem={mem_limit_gb:.1f}gb {num_procs=} {batch_size=}"
        )
        return num_procs, batch_size

    def _halve_batches(self, batches):
        """Half the size of retried batches."""
        old_num_batches = len(batches)
        half_batches = {}
        for batch_num, batch_pks in batches.items():
            if not batch_pks:
                continue
            batch_num_a = batch_num * 2
            if len(batch_pks) == 1:
                half_batches[batch_num_a] = batch_pks
                continue
            halfway = int(len(batch_pks) / 2)
            half_batches[batch_num_a] = batch_pks[:halfway]
            batch_num_b = batch_num_a + 1
            half_batches[batch_num_b] = batch_pks[halfway:]
        batches = half_batches
        self.log.debug(f"Split {old_num_batches} batches into {len(batches)}.")
        return batches

    def _apply_batches(self, pool, batches, backend):
        """Apply the batches to the process pool."""
        results = {}
        for batch_num, batch_pks in batches.items():
            args = (None, batch_pks)
            kwd = {"batch_num": batch_num}
            result = pool.apply_async(backend.update, args, kwd)
            results[batch_num] = (result, batch_pks)
        pool.close()
        self.log.debug(f"Search index update queued {len(results)} batches...")
        return results

    def _collect_results(self, results, complete, num_comics, since):
        """Collect results from the process pool."""
        retry_batches = {}
        for batch_num, (result, batch_pks) in results.items():
            try:
                complete += result.get()
                since = self.status_controller.update(
                    SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
                    complete,
                    num_comics,
                    since=since,
                )
            except (DatabaseError, SearchFieldError):
                self.log.warning(
                    f"Search index update needs to retry batch {batch_num}"
                )
                retry_batches[batch_num] = batch_pks
            except Exception as exc:
                self.log.error(f"Search index update batch failed: {batch_num} {exc}")
                self.log.exception(exc)
        return retry_batches, complete

    def _try_update_batch(
        self, backend, batches, num_procs, num_comics, batch_size, complete, attempt
    ):
        """Attempt to update batches, with reursive retry."""
        since = time()
        if attempt > 1:
            batches = self._halve_batches(batches)

        self.log.debug(
            f"Search index updating {len(batches)} batches, attempt {attempt}"
        )
        procs = min(num_procs, len(batches))
        pool = Pool(procs, maxtasksperchild=1)
        results = self._apply_batches(pool, batches, backend)
        retry_batches, complete = self._collect_results(
            results, complete, num_comics, since
        )
        pool.join()

        if not retry_batches:
            return

        if attempt < self._MAX_RETRIES:
            self._try_update_batch(
                backend,
                retry_batches,
                num_procs,
                num_comics,
                batch_size,
                complete,
                attempt + 1,
            )
        else:
            total = len(retry_batches) * batch_size
            self.log.error(
                f"Search Indexer failed to update {total} comics"
                f"in {len(retry_batches)} batches."
            )

    @staticmethod
    def _get_update_batches(qs, batch_size, num_comics, num_procs):
        all_pks = qs.order_by("updated_at", "pk").values_list("pk", flat=True)
        start = 0
        end = start
        batch_num = 0
        procs = int(min(num_procs, num_comics / batch_size))
        using_more_than_half_procs = procs * 2 > num_procs

        batches = {}
        while start < num_comics:
            if batch_num < procs and using_more_than_half_procs:
                # XXX hack to avoid first batch retries
                end = int(end / 2)
            batches[batch_num] = all_pks[start:end]
            start = end + 1
            end = start + batch_size
            batch_num += 1
        return batches

    def _mp_update(self, backend, qs):
        # Init
        start_time = time()
        try:
            num_comics = qs.count()
            self.status_controller.start(
                SearchIndexStatusTypes.SEARCH_INDEX_UPDATE, complete=0, total=num_comics
            )

            num_procs, batch_size = self._get_throttle_params(num_comics)
            batches = self._get_update_batches(qs, batch_size, num_comics, num_procs)
            self._try_update_batch(
                backend, batches, num_procs, num_comics, batch_size, 0, 1
            )

            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            cps = int(num_comics / elapsed_time)
            self.log.info(
                f"Search engine updated {num_comics} comics"
                f" in {elapsed} at {cps} comics per second."
            )
        except Exception as exc:
            self.log.error(f"Update search index with multiprocessing: {exc}")
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
            # Clear
            if rebuild:
                self.log.info("Rebuilding search index...")
                backend.clear(commit=True)
                self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
                self.log.info("Old search index cleared.")

            # Update
            backend.setup(False)

            # num_procs = 2 # TODO: hack
            # if num_procs > 0:
            #    close_old_connections() # TODO see comment in haystack
            qs = self._get_queryset(backend, rebuild)
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
