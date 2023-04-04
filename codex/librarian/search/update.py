"""Search Index update."""
from datetime import datetime
from math import ceil
from multiprocessing import Pool, cpu_count
from time import time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from django.db.models import Q
from haystack.exceptions import SearchFieldError
from haystack.indexes import DJANGO_ID
from humanize import naturaldelta
from whoosh.query import Every

from codex.librarian.search.remove import RemoveMixin
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import SearchIndexRemoveStaleTask
from codex.memory import get_mem_limit
from codex.models import Comic, Library
from codex.settings.settings import CPU_MULTIPLIER
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
    _CPU_MULTIPLIER = CPU_MULTIPLIER

    def _init_statuses(self, rebuild):
        """Initialize all statuses order before starting."""
        statii = []
        if rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)]
        statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_UPDATE)]
        if not rebuild:
            statii += [Status(SearchIndexStatusTypes.SEARCH_INDEX_REMOVE)]
        self.status_controller.start_many(statii)

    def _get_queryset_from_search_results(self, results, qs, suffix):
        """Use python to find the lowest date and any missing rows."""
        all_index_pks = []
        index_latest_updated_at = self._MIN_UTC_DATE
        for result in results:
            all_index_pks.append(result.get(DJANGO_ID))
            result_updated_at = result.get("updated_at")
            if result_updated_at > index_latest_updated_at:
                index_latest_updated_at = result_updated_at
        if index_latest_updated_at > self._MIN_UTC_DATE:
            qs = qs.filter(
                Q(updated_at__gt=index_latest_updated_at) | ~Q(pk__in=all_index_pks)
            )
            suffix = f"since {index_latest_updated_at}"

        return qs, suffix

    def _get_queryset_from_search_index(self, backend, qs, suffix):
        """Get the date of the last updated item in the search index."""
        with backend.index.refresh().searcher() as searcher:
            # XXX IDK why but sorting by 'updated_at' removes the latest and most valuable result
            #     So I have to do it in my own method.
            #     Because of this I've turned of sortable in the schema.
            results = searcher.search(Every(), reverse=True, scored=False)
            if results.scored_length():
                qs, suffix = self._get_queryset_from_search_results(results, qs, suffix)

        return qs, suffix

    def _get_queryset(self, backend, rebuild):
        """Rebuild or set up update."""
        qs = Comic.objects.all()

        suffix = "with all comics"
        if not rebuild:
            qs, suffix = self._get_queryset_from_search_index(backend, qs, suffix)

        self.log.info(f"Updating search index {suffix}...")
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
        cpu_max = ceil(mem_limit_gb * self._CPU_MULTIPLIER)
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
        """Half the size of retried batches.

        Helps if it was a memory issue.
        If it's a data issue then it binary searches down to the real problem.
        """
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
            except self._EXPECTED_EXCEPTIONS:
                pass
            except Exception:
                reason = f"Search Index Update collect result batch {batch_num}"
                self.log.exception(reason)
            else:
                # success
                continue

            # failure
            self.log.debug(f"Search index update will retry batch {batch_num}")
            retry_batches[retry_batch_num] = batch_pks
            retry_batch_num += 1

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

    @staticmethod
    def _get_update_batches(qs, batch_size, num_comics):
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
        except Exception:
            self.log.exception("Update search index")
        finally:
            until = start_time + 1
            self.status_controller.finish_many(self._STATUS_FINISH_TYPES, until=until)
