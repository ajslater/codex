"""Search Index update."""
from datetime import datetime
from math import ceil
from multiprocessing import Pool, cpu_count
from time import time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from haystack.exceptions import SearchFieldError
from humanize import naturaldelta
from whoosh.query import Every

from codex.librarian.search.remove import RemoveMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import SearchIndexRemoveStaleTask
from codex.memory import get_mem_limit
from codex.models import Comic, Library
from codex.status import Status

if TYPE_CHECKING:
    from codex.search.backend import CodexSearchBackend


class UpdateMixin(RemoveMixin):
    """Search Index update methods."""

    _STATUS_FINISH_TYPES = (
        SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
        SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
    )
    _MIN_UTC_DATE = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
    _MIN_BATCH_SIZE = 1
    # A larger batch size might be slightly faster for very large
    # indexes and require less optimization later, but steady progress
    # updates are better UX.
    _MAX_BATCH_SIZE = 640
    _EXPECTED_EXCEPTIONS = (
        DatabaseError,
        IndexError,
        ObjectDoesNotExist,
        SearchFieldError,
    )
    _MAX_RETRIES = 8

    def _init_statuses(self, rebuild):
        """Initialize all statuses order before starting."""
        statii = []
        if rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)]
        statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_UPDATE)]
        if not rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)]
        self.status_controller.start_many(statii)

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
        with backend.index.refresh().searcher() as searcher:
            # XXX IDK why but sorting by 'updated_at' removes the latest and most valuable result
            #     So I have to do it in my own method.
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
            if start_date:
                qs = qs.filter(updated_at__gt=start_date)

        self.log.info(f"Updating search index since {start_date}...")

        return qs

    def _get_throttle_params(self, num_comics):
        """Get params based on memory and total number of comics.

        >4GB is normal.
        <=2GB is constrained.
        """
        mem_limit_gb = get_mem_limit("g")

        # max procs
        # throttle multiprocessing in lomem environments.
        # each process running has significant memory overhead.
        cpu_max = ceil(mem_limit_gb * 4 / 3 + 2 / 3)
        max_procs = min(cpu_count(), cpu_max)

        batch_size = int(
            max(
                self._MIN_BATCH_SIZE,
                min(num_comics / max_procs, self._MAX_BATCH_SIZE),
            )
        )

        num_procs = int(min(max(1, num_comics / batch_size), max_procs))

        opts = {
            "comics": num_comics,
            "memgb": mem_limit_gb,
            "procs": num_procs,
            "batch_size": batch_size,
        }
        self.log.debug(f"Search Index update opts: {opts}")
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
            kwd = {"batch_num": batch_num, "abort_event": self.abort_event}
            result = pool.apply_async(backend.update, args, kwd)
            results[batch_num] = (result, batch_pks)
        pool.close()
        self.log.debug(f"Search index update queued {len(results)} batches...")
        return results

    def _collect_results(self, results, complete, status):
        """Collect results from the process pool."""
        retry_batches = {}
        retry_batch_num = 0
        if self.abort_event.is_set():
            return retry_batches, retry_batch_num

        num_results = len(results)
        for batch_num, (result, batch_pks) in results.items():
            try:
                complete += result.get()
                self.log.debug(
                    f"Search index batch {batch_num}/{num_results} complete: "
                    f"{status.complete}/{status.total} comics"
                )
                status.complete = complete
                self.status_controller.update(status)
            except Exception as exc:
                retry_batches[retry_batch_num] = batch_pks
                self.log.warning(f"Search index update will retry batch {batch_num}")
                retry_batch_num += 1
                if not isinstance(exc, self._EXPECTED_EXCEPTIONS):
                    self.log.exception("Search index update - collect batch results")
        return retry_batches, complete

    def _try_update_batch(self, backend, batch_info, status):
        """Attempt to update batches, with reursive retry."""
        (
            batches,
            num_procs,
            num_comics,
            batch_size,
            complete,
            attempt,
        ) = batch_info
        if self.abort_event.is_set():
            return complete

        if attempt > 1:
            batches = self._halve_batches(batches)

        num_batches = len(batches)
        if not num_batches:
            self.log.debug("Search index nothing to update.")
            return complete
        self.log.debug(
            f"Search index updating {num_batches} batches, attempt {attempt}"
        )
        procs = min(num_procs, num_batches)
        pool = Pool(procs, maxtasksperchild=1)
        results = self._apply_batches(pool, batches, backend)
        retry_batches, complete = self._collect_results(results, complete, status)
        pool.join()

        num_successful_batches = num_batches - len(retry_batches)

        ratio = 100 * (num_successful_batches / num_batches)
        self.log.debug(
            f"Search Index attempt {attempt} batch success ratio: {round(ratio)}%"
        )
        if not retry_batches:
            return complete

        if attempt < self._MAX_RETRIES:
            batch_info = (
                retry_batches,
                num_procs,
                num_comics,
                batch_size,
                complete,
                attempt + 1,
            )
            complete = self._try_update_batch(backend, batch_info, status)
        else:
            total = len(retry_batches) * batch_size
            self.log.error(
                f"Search Indexer failed to update {total} comics"
                f"in {len(retry_batches)} batches."
            )
        return complete

    @staticmethod
    def _get_update_batch_end_index(start, batch_size, batch_num, procs):
        if batch_num < procs:
            # Gets early results to the status update
            # by making small batches in the beginning.
            end = start + int(batch_size * (batch_num / procs))
        else:
            end = start + batch_size
        return end

    @classmethod
    def _get_update_batches(cls, qs, batch_size, num_comics):
        all_pks = qs.order_by("updated_at", "pk").values_list("pk", flat=True)
        batch_num = 0
        start = 0
        end = start + batch_size

        batches = {}
        while start < num_comics:
            batches[batch_num] = all_pks[start:end]
            batch_num += 1
            start = end
            end = start + batch_size
        return batches

    def _mp_update(self, backend, qs):
        # Init
        start_time = time()
        num_comics = qs.count()
        if not num_comics or self.abort_event.is_set():
            return
        status = Status(SearchIndexStatusTypes.SEARCH_INDEX_UPDATE, 0, num_comics)
        try:
            self.status_controller.start(status)

            num_procs, batch_size = self._get_throttle_params(num_comics)
            batches = self._get_update_batches(qs, batch_size, num_comics)
            batch_info = (batches, num_procs, num_comics, batch_size, 0, 1)
            complete = self._try_update_batch(
                backend,
                batch_info,
                status,
            )

            # Log performance
            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            cps = int(complete / elapsed_time)
            self.log.info(
                f"Search engine updated {complete} comics"
                f" in {elapsed} at {cps} comics per second."
            )
        except Exception:
            self.log.exception("Update search index with multiprocessing")
        finally:
            until = start_time + 1
            self.status_controller.finish(status, until=until)

    def update_search_index(self, rebuild=False):
        """Update or Rebuild the search index."""
        start_time = time()
        self.abort_event.clear()
        try:
            any_update_in_progress = Library.objects.filter(
                update_in_progress=True
            ).exists()
            if any_update_in_progress:
                self.log.debug(
                    "Database update in progress, not updating search index yet."
                )
                return

            if not rebuild and not self.is_search_index_uuid_match():
                rebuild = True

            self._init_statuses(rebuild)

            backend: CodexSearchBackend = self.engine.get_backend()  # type: ignore
            # Clear
            if rebuild:
                self.log.info("Rebuilding search index...")
                clear_status = Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
                self.status_controller.start(clear_status)
                backend.clear(commit=True)
                self.status_controller.finish(clear_status)
                self.log.info("Old search index cleared.")

            # Update
            backend.setup(False)
            if self.abort_event.is_set():
                return
            qs = self._get_queryset(backend, rebuild)
            self._mp_update(backend, qs)

            # Finish
            if rebuild:
                self.set_search_index_version()
            else:
                task = SearchIndexRemoveStaleTask()
                self.librarian_queue.put(task)

            elapsed_time = time() - start_time
            elapsed = naturaldelta(elapsed_time)
            self.log.info(f"Search index updated in {elapsed}.")
        except MemoryError:
            self.log.warning("Search index needs more memory to update.")
            self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)
        except Exception:
            self.log.exception("Update search index")
            self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)
        finally:
            # Finishing these tasks inside the command process leads to a timing
            # misalignment. Finish it here works.
            until = start_time + 1
            self.status_controller.finish_many(self._STATUS_FINISH_TYPES, until=until)
