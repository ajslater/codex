"""Library process worker for background tasks."""

from multiprocessing import Manager, Process
from threading import active_count
from types import MappingProxyType
from typing import NamedTuple

from caseconverter import snakecase

from codex.librarian.bookmark.bookmarkd import BookmarkThread
from codex.librarian.bookmark.tasks import BookmarkTask
from codex.librarian.covers.coverd import CoverThread
from codex.librarian.covers.tasks import CoverTask
from codex.librarian.cron.crond import CronThread
from codex.librarian.delayed_taskd import DelayedTasksThread
from codex.librarian.importer.importerd import ComicImporterThread
from codex.librarian.importer.tasks import (
    AdoptOrphanFoldersTask,
    ImportTask,
)
from codex.librarian.janitor.janitor import Janitor
from codex.librarian.janitor.tasks import JanitorTask
from codex.librarian.notifier.notifierd import NotifierThread
from codex.librarian.notifier.tasks import NotifierTask
from codex.librarian.search.searchd import SearchIndexerThread
from codex.librarian.search.tasks import (
    SearchIndexAbortTask,
    SearchIndexerTask,
    SearchIndexUpdateTask,
)
from codex.librarian.tasks import DelayedTasks, LibrarianShutdownTask, WakeCronTask
from codex.librarian.telemeter.tasks import TelemeterTask
from codex.librarian.telemeter.telemeter import send_telemetry
from codex.librarian.watchdog.event_batcherd import WatchdogEventBatcherThread
from codex.librarian.watchdog.observers import (
    LibraryEventObserver,
    LibraryPollingObserver,
)
from codex.librarian.watchdog.tasks import (
    WatchdogEventTask,
    WatchdogPollLibrariesTask,
    WatchdogSyncTask,
)
from codex.logger_base import LoggerBaseMixin


class LibrarianDaemon(Process, LoggerBaseMixin):
    """Librarian Process."""

    _THREAD_CLASSES = (
        BookmarkThread,
        NotifierThread,
        DelayedTasksThread,
        CoverThread,
        SearchIndexerThread,
        ComicImporterThread,
        WatchdogEventBatcherThread,
        LibraryEventObserver,
        LibraryPollingObserver,
        CronThread,
    )
    _THREAD_CLASS_MAP = MappingProxyType(
        {
            snakecase(thread_class.__name__): thread_class
            for thread_class in _THREAD_CLASSES
        }
    )
    LibrarianThreads = NamedTuple("LibrarianThreads", _THREAD_CLASS_MAP.items())

    proc = None

    def __init__(self, queue, log_queue, broadcast_queue):
        """Init process."""
        name = self.__class__.__name__
        super().__init__(name=name, daemon=False)
        self.queue = queue
        self.log_queue = log_queue
        self.broadcast_queue = broadcast_queue
        startup_tasks = (
            AdoptOrphanFoldersTask(),
            WatchdogSyncTask(),
            SearchIndexUpdateTask(False),
        )

        for task in startup_tasks:
            self.queue.put(task)
        self.search_indexer_abort_event = Manager().Event()

    def _process_task(self, task):  # noqa: PLR0912,C901
        """Process an individual task popped off the queue."""
        match task:
            case CoverTask():
                self._threads.cover_thread.queue.put(task)
            case BookmarkTask():
                self._threads.bookmark_thread.queue.put(task)
            case WatchdogEventTask():
                self._threads.watchdog_event_batcher_thread.queue.put(task)
            case ImportTask():
                self._threads.comic_importer_thread.queue.put(task)
            case NotifierTask():
                self._threads.notifier_thread.queue.put(task)
            case WatchdogSyncTask():
                for observer in self._observers:
                    observer.sync_library_watches()
            case WatchdogPollLibrariesTask():
                self._threads.library_polling_observer.poll(
                    task.library_ids, task.force
                )
            case SearchIndexAbortTask():
                # Must come before the generic SearchIndexerTask below
                self.search_indexer_abort_event.set()
                self.log.debug("Told search indexers to stop for db updates.")
            case SearchIndexerTask():
                self._threads.search_indexer_thread.queue.put(task)
            case WakeCronTask():
                self._threads.cron_thread.end_timeout()
            case TelemeterTask():
                send_telemetry(self.log)
            case JanitorTask():
                self.janitor.run(task)
            case DelayedTasks():
                self._threads.delayed_tasks_thread.queue.put(task)
            case LibrarianShutdownTask():
                self.log.info(f"Shutting down {self.__class__.__name__}...")
                self.run_loop = False
            case _:
                self.log.warning(f"Unhandled Librarian task: {task}")

    def _create_threads(self):
        """Create all the threads."""
        self.log.debug("Creating Librarian threads...")
        self.log.debug(f"Active threads before thread creation: {active_count()}")
        threads = {}
        kwargs = {"librarian_queue": self.queue, "log_queue": self.log_queue}
        for name, thread_class in self._THREAD_CLASS_MAP.items():
            if thread_class == NotifierThread:
                thread = thread_class(self.broadcast_queue, **kwargs)
            elif thread_class == SearchIndexerThread:
                thread = thread_class(self.search_indexer_abort_event, **kwargs)
            else:
                thread = thread_class(**kwargs)
            threads[name] = thread
            self.log.debug(f"Created {name} thread.")
        self._threads = self.LibrarianThreads(**threads)
        self._observers = (
            self._threads.library_event_observer,
            self._threads.library_polling_observer,
        )
        self.log.debug("Threads created")

    def _start_threads(self):
        """Start all librarian's threads."""
        self.log.debug(f"{self.__class__.__name__} starting all threads.")
        for thread in self._threads:
            thread.start()
        self.log.info(f"{self.__class__.__name__} started all threads.")

    def _startup(self):
        """Initialize threads."""
        self.init_logger(self.log_queue)
        self.log.debug(f"Started {self.__class__.__name__}.")
        self.janitor = Janitor(self.log_queue, self.queue)
        self._create_threads()  # can't do this in init.
        self._start_threads()
        self.run_loop = True
        self.log.info(f"{self.__class__.__name__} ready for tasks.")

    def _stop_threads(self):
        """Stop all librarian's threads."""
        self.log.debug(f"{self.__class__.__name__} stopping all threads...")
        for thread in self._reversed_threads:
            thread.stop()
        self.log.debug(f"{self.__class__.__name__} stopped all threads.")

    def _join_threads(self):
        """Join all librarian threads."""
        self.log.debug(f"{self.__class__.__name__} joining all threads...")
        for thread in self._reversed_threads:
            thread.join()
        self.log.info(f"{self.__class__.__name__} joined all threads.")

    def _shutdown(self):
        """Shutdown threads and queues."""
        self._reversed_threads = reversed(self._threads)
        self._stop_threads()
        self._join_threads()
        while not self.queue.empty():
            self.queue.get_nowait()
        self.queue.close()
        self.queue.join_thread()
        self.log.info(f"{self.__class__.__name__} finished.")
        self.log_queue.close()
        self.log_queue.join_thread()

    def run(self):
        """Process tasks from the queue.

        This process also runs the crond thread and the Watchdog Observer
        threads.
        """
        self._startup()
        try:
            while self.run_loop:
                try:
                    task = self.queue.get()
                    self._process_task(task)
                except Exception:
                    self.log.exception(f"In {self.__class__.__name__} loop")
        except Exception:
            self.log.exception(f"{self.__class__.__name__} crashed.")
        except KeyboardInterrupt:
            self.log.debug(f"{self.__class__.__name__} Keyboard interrupt")
        finally:
            self._shutdown()

    def stop(self):
        """Close up the librarian process."""
        self.queue.put(LibrarianShutdownTask())
        self.queue.close()
        self.queue.join_thread()
        self.join()
        self.close()
