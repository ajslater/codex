"""Haystack Search index updater."""
from datetime import datetime
from time import time
from uuid import uuid4

from haystack import connections as haystack_connections
from haystack.constants import DJANGO_ID
from humanize import naturaldelta
from whoosh.query import Every, Or
from whoosh.query.terms import Term

from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.search.tasks import (
    SearchIndexOptimizeTask,
    SearchIndexRebuildIfDBChangedTask,
    SearchIndexUpdateTask,
)
from codex.models import Comic, Library, Timestamp
from codex.search.backend import CodexSearchBackend
from codex.search.engine import CodexSearchEngine
from codex.settings.settings import SEARCH_INDEX_PATH, SEARCH_INDEX_UUID_PATH
from codex.threads import QueuedThread

VERBOSITY = 2  # 1
REBUILD_ARGS = ("rebuild_index",)
BATCH_SIZE = 1000000
REBUILD_KWARGS = {
    "interactive": False,
    "verbosity": VERBOSITY,
    "batch_size": BATCH_SIZE,
}
UPDATE_ARGS = ("update_index", "codex")
UPDATE_KWARGS = {
    "remove": True,
    "verbosity": VERBOSITY,
    "batch_size": BATCH_SIZE,
}
MIN_FINISHED_TIME = 1
# Docker constraints look like 3 comics per second.
# Don't optimize if it might take longer than 20 minutes.
# Can be much faster running native. 128 comics per second for instance.
OPTIMIZE_DOC_COUNT = 20 * 60 * 3


class SearchIndexerThread(QueuedThread):
    """A worker to handle search index update tasks."""

    STATUS_FINISH_TYPES = frozenset(
        (
            SearchIndexStatusTypes.SEARCH_INDEX_CLEAR,
            SearchIndexStatusTypes.SEARCH_INDEX_UPDATE,
            SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE,
            SearchIndexStatusTypes.SEARCH_INDEX_REMOVE,
        )
    )

    def _set_search_index_version(self):
        """Set the codex db to search index matching id."""
        version = str(uuid4())
        try:
            lv = Timestamp.objects.get(name=Timestamp.SEARCH_INDEX_UUID)
            lv.version = version
            lv.save()
            SEARCH_INDEX_PATH.mkdir(parents=True, exist_ok=True)
            with SEARCH_INDEX_UUID_PATH.open("w") as uuid_file:
                uuid_file.write(version)
        except Exception as exc:
            self.log.error(f"Setting search index to db synchronization token: {exc}")

    def _is_search_index_uuid_match(self):
        """Is this search index for this database."""
        result = False
        try:
            with SEARCH_INDEX_UUID_PATH.open("r") as uuid_file:
                version = uuid_file.read()
            result = Timestamp.objects.filter(
                name=Timestamp.SEARCH_INDEX_UUID, version=version
            ).exists()
        except (FileNotFoundError, Timestamp.DoesNotExist):
            pass
        except Exception as exc:
            self.log.exception(exc)
        return result

    def _get_stale_doc_ids(self, qs, backend, start_date):
        """Get the stale search index pks that are no longer in the database."""
        start = time()
        self.status_controller.start(SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE, 0)
        try:
            self.log.debug("Looking for stale records...")

            if start_date:
                # if start date then use the entire index.
                qs = Comic.objects

            database_pks = qs.values_list("pk", flat=True)
            mask = Or([Term(DJANGO_ID, str(pk)) for pk in database_pks])

            backend.index.refresh()
            with backend.index.searcher() as searcher:
                results = searcher.search(Every(), limit=None, mask=mask)
                doc_ids = results.docs()
            return doc_ids
        finally:
            until = start + 1
            self.status_controller.finish(
                SearchIndexStatusTypes.SEARCH_INDEX_FIND_REMOVE, until=until
            )

    def _remove_stale_records(self, qs, backend, start_date):
        """Remove records not in the database from the index."""
        try:
            stale_doc_ids = self._get_stale_doc_ids(qs, backend, start_date)
            backend.remove_batch(stale_doc_ids)
        except Exception as exc:
            self.log.error("While removing stale records:")
            self.log.exception(exc)

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

            queue_kwargs = {
                "log_queue": self.log_queue,
                "librarian_queue": self.librarian_queue,
            }
            engine = CodexSearchEngine(queue_kwargs=queue_kwargs)
            backend = engine.get_backend()

            unified_index = engine.get_unified_index()
            index = unified_index.get_index(Comic)

            if rebuild:
                self.log.info("Rebuilding search index...")
                backend.clear(models=[Comic], commit=True)
                self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_CLEAR)
                start_date = None
            else:
                start_date = Timestamp.objects.get(
                    name=Timestamp.SEARCH_INDEX
                ).updated_at
                self.log.info(f"Updating search index since {start_date}...")

            qs = index.build_queryset(using=backend, start_date=start_date).order_by(
                "pk"
            )

            backend.update(index, qs, commit=True)

            Timestamp.touch(Timestamp.SEARCH_INDEX)
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
            self.status_controller.finish_many(self.STATUS_FINISH_TYPES, until=until)

    def _rebuild_search_index_if_db_changed(self):
        """Rebuild the search index if the db changed."""
        if not self._is_search_index_uuid_match():
            self.log.warning("Database does not match search index.")
            task = SearchIndexUpdateTask(True)
            self.librarian_queue.put(task)
        else:
            self.log.info("Database matches search index.")

    def _optimize_search_index(self, force=False):
        """Optimize search index."""
        try:
            self.status_controller.start(
                type=SearchIndexStatusTypes.SEARCH_INDEX_OPTIMIZE
            )
            self.log.debug("Optimizing search index...")
            start = datetime.now()
            num_segments = len(tuple(SEARCH_INDEX_PATH.glob("*.seg")))
            if num_segments <= 1:
                self.log.info("Search index already optimized.")
                return
            backends = haystack_connections.connections_info.keys()
            for conn_key in backends:
                backend = haystack_connections[conn_key].get_backend()
                if not backend.setup_complete:
                    backend.setup()
                backend.index = backend.index.refresh()
                num_docs = backend.index.doc_count()
                if num_docs > OPTIMIZE_DOC_COUNT and not force:
                    self.log.info(
                        f"Search index > {OPTIMIZE_DOC_COUNT} comics. Not optimizing."
                    )
                    return
                self.log.info(
                    f"Search index found in {num_segments} segments, optmizing..."
                )
                writerargs = CodexSearchBackend.WRITERARGS
                backend.index.optimize(**writerargs)
                elapsed_delta = datetime.now() - start
                elapsed = naturaldelta(elapsed_delta)
                cps = int(num_docs / elapsed_delta.total_seconds())
                self.log.info(
                    f"Optimized search index in {elapsed} at {cps} comics per second."
                )
        finally:
            self.status_controller.finish(SearchIndexStatusTypes.SEARCH_INDEX_OPTIMIZE)

    def process_item(self, task):
        """Run the updater."""
        if isinstance(task, SearchIndexRebuildIfDBChangedTask):
            self._rebuild_search_index_if_db_changed()
        elif isinstance(task, SearchIndexUpdateTask):
            self._update_search_index(rebuild=task.rebuild)
        elif isinstance(task, SearchIndexOptimizeTask):
            self._optimize_search_index(task.force)
        else:
            self.log.warning(f"Bad task sent to search index thread: {task}")
