"""Library process worker for background tasks."""
from collections import namedtuple
from multiprocessing import Process
from threading import active_count

from caseconverter import snakecase

from codex.librarian.covers.coverd import CoverCreatorThread
from codex.librarian.covers.tasks import CoverTask
from codex.librarian.delayed_taskd import DelayedTasksThread
from codex.librarian.importer.importerd import ComicImporterThread
from codex.librarian.importer.tasks import AdoptOrphanFoldersTask, UpdaterTask
from codex.librarian.janitor.janitor import Janitor
from codex.librarian.janitor.janitord import JanitorThread
from codex.librarian.janitor.tasks import JanitorTask
from codex.librarian.notifier.notifierd import NotifierThread
from codex.librarian.notifier.tasks import NotifierTask
from codex.librarian.search.searchd import SearchIndexerThread
from codex.librarian.search.tasks import (
    SearchIndexerTask,
    SearchIndexRebuildIfDBChangedTask,
)
from codex.librarian.tasks import DelayedTasks
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

LIBRARIAN_SHUTDOWN_TASK = "shutdown"


class LibrarianDaemon(Process, LoggerBaseMixin):
    """Librarian Process."""

    _THREAD_CLASSES = (
        NotifierThread,
        DelayedTasksThread,
        CoverCreatorThread,
        SearchIndexerThread,
        ComicImporterThread,
        WatchdogEventBatcherThread,
        LibraryEventObserver,
        LibraryPollingObserver,
        JanitorThread,
    )
    _THREAD_CLASS_MAP = {
        snakecase(thread_class.__name__): thread_class
        for thread_class in _THREAD_CLASSES
    }
    LibrarianThreads = namedtuple("LibrarianThreads", _THREAD_CLASS_MAP.keys())

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
            SearchIndexRebuildIfDBChangedTask(),
            WatchdogSyncTask(),
        )
        for task in startup_tasks:
            self.queue.put(task)

    def _process_task(self, task):
        """Process an individual task popped off the queue."""
        if isinstance(task, CoverTask):
            self._threads.cover_creator_thread.queue.put(task)
        elif isinstance(task, WatchdogEventTask):
            self._threads.watchdog_event_batcher_thread.queue.put(task)
        elif isinstance(task, UpdaterTask):
            self._threads.comic_importer_thread.queue.put(task)
        elif isinstance(task, NotifierTask):
            self._threads.notifier_thread.queue.put(task)
        elif isinstance(task, WatchdogSyncTask):
            for observer in self._observers:
                observer.sync_library_watches()
        elif isinstance(task, WatchdogPollLibrariesTask):
            self._threads.library_polling_observer.poll(task.library_ids, task.force)
        elif isinstance(task, SearchIndexerTask):
            self._threads.search_indexer_thread.queue.put(task)
        elif isinstance(task, JanitorTask):
            self.janitor.run(task)
        elif isinstance(task, DelayedTasks):
            self._threads.delayed_tasks_thread.queue.put(task)
        elif task == LIBRARIAN_SHUTDOWN_TASK:
            self.log.info(f"Shutting down {self.__class__.__name__}...")
            self.run_loop = False
        else:
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

    def run(self):
        """Process tasks from the queue.

        This process also runs the crond thread and the Watchdog Observer
        threads.
        """
        self.init_logger(self.log_queue)
        self.log.debug(f"Started {self.__class__.__name__}.")
        self.janitor = Janitor(self.log_queue, self.queue)
        self._create_threads()  # can't do this in init.
        self._start_threads()
        self.run_loop = True
        self.log.info(f"{self.__class__.__name__} ready for tasks.")
        try:
            while self.run_loop:
                try:
                    task = self.queue.get()
                    self._process_task(task)
                except Exception as exc:
                    self.log.error(f"Error in {self.__class__.__name__} loop")
                    self.log.exception(exc)
        except Exception as exc:
            self.log.error(f"{self.__class__.__name__} crashed.")
            self.log.exception(exc)
        except KeyboardInterrupt:
            self.log.debug(f"{self.__class__.__name__} Keyboard interrupt")
        finally:
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

    def stop(self):
        """Close up the librarian process."""
        self.queue.put(LIBRARIAN_SHUTDOWN_TASK)
        self.queue.close()
        self.queue.join_thread()
        self.join()
        self.close()
