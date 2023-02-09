"""Library process worker for background tasks."""
import re

from multiprocessing import Process
from threading import active_count

from codex.librarian.covers.coverd import CoverCreator
from codex.librarian.covers.tasks import CoverTask
from codex.librarian.crond import Crond
from codex.librarian.db.tasks import AdoptOrphanFoldersTask, UpdaterTask
from codex.librarian.db.updaterd import Updater
from codex.librarian.delayed_taskd import DelayedTasksThread
from codex.librarian.janitor.janitor import Janitor
from codex.librarian.janitor.tasks import JanitorTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.notifierd import NotifierThread
from codex.librarian.notifier.tasks import NotifierTask
from codex.librarian.search.searchd import SearchIndexer
from codex.librarian.search.tasks import (
    SearchIndexerTask,
    SearchIndexRebuildIfDBChangedTask,
)
from codex.librarian.tasks import DelayedTasks
from codex.librarian.watchdog.eventsd import EventBatcher
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

    SHUTDOWN_TIMEOUT = 5
    MAX_WS_ATTEMPTS = 5
    SHUTDOWN_TASK = "shutdown"
    THREAD_CLASSES = (
        NotifierThread,
        DelayedTasksThread,
        CoverCreator,
        SearchIndexer,
        Updater,
        EventBatcher,
        LibraryEventObserver,
        LibraryPollingObserver,
        Crond,
    )
    CAMEL_TO_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")

    proc = None

    def __init__(self, queue, log_queue):
        """Init process."""
        name = self.__class__.__name__
        super().__init__(name=name, daemon=False)
        self.init_logger(log_queue)
        self.queue = queue
        startup_tasks = (
            AdoptOrphanFoldersTask(),
            SearchIndexRebuildIfDBChangedTask(),
            WatchdogSyncTask(),
        )
        for task in startup_tasks:
            self.queue.put(task)

    @classmethod
    def _camel_to_snake_case(cls, name):
        return cls.CAMEL_TO_SNAKE_RE.sub("_", name).lower()

    def _process_task(self, task):
        """Process an individual task popped off the queue."""
        run = True
        if isinstance(task, CoverTask):
            self._threads["cover_creator"].queue.put(task)
        elif isinstance(task, WatchdogEventTask):
            self._threads["event_batcher"].queue.put(task)
        elif isinstance(task, UpdaterTask):
            self._threads["updater"].queue.put(task)
        elif isinstance(task, NotifierTask):
            self._threads["notifier_thread"].queue.put(task)
        elif isinstance(task, WatchdogSyncTask):
            for observer in self._observers:
                observer.sync_library_watches()
        elif isinstance(task, WatchdogPollLibrariesTask):
            self._threads["library_polling_observer"].poll(task.library_ids, task.force)
        elif isinstance(task, SearchIndexerTask):
            self._threads["search_indexer"].queue.put(task)
        elif isinstance(task, JanitorTask):
            self.janitor.run(task)
        elif isinstance(task, DelayedTasks):
            self._threads["delayed_tasks_thread"].queue.put(task)
        elif task == self.SHUTDOWN_TASK:
            self.log.info("Shutting down Librarian...")
            run = False
        else:
            self.log.warning(f"Unhandled Librarian task: {task}")
        return run

    def _create_threads(self):
        """Create all the threads."""
        self.log.debug("Creating Librarian threads...")
        self.log.debug(f"Active threads before thread creation: {active_count()}")
        self._threads = {}
        kwargs = {"librarian_queue": self.queue, "log_queue": self.log_queue}
        for thread_class in self.THREAD_CLASSES:
            name = getattr(thread_class, "NAME", thread_class.__name__)
            thread = thread_class(**kwargs)
            name = self._camel_to_snake_case(name)
            self._threads[name] = thread
            self.log.debug(f"Created {name} thread.")
        self._observers = (
            self._threads["library_event_observer"],
            self._threads["library_polling_observer"],
        )
        self.log.debug("Threads created")

    def _start_threads(self):
        """Start all librarian's threads."""
        self.log.debug(f"Starting all {self.__class__.__name__} threads.")
        for thread in self._threads.values():
            thread.start()
        self.log.info(f"Started all {self.__class__.__name__} threads.")

    def _stop_threads(self):
        """Stop all librarian's threads."""
        self.log.debug(f"Stopping all {self.__class__.__name__} threads...")
        reversed_threads = reversed(self._threads.values())
        for thread in reversed_threads:
            thread.stop()
        self.log.debug(f"Stopped all {self.__class__.__name__} threads.")
        self.log.debug(f"Joining all {self.__class__.__name__} threads...")
        for thread in reversed_threads:
            thread.join()
        self.log.info(f"Joined all {self.__class__.__name__} threads.")

    def run(self):
        """
        Process tasks from the queue.

        This process also runs the crond thread and the Watchdog Observer
        threads.
        """
        try:
            self.log.debug("Started Librarian process.")
            self.janitor = Janitor(self.log_queue, self.queue)
            self._create_threads()  # can't do this in init.
            self._start_threads()
            run = True
            self.log.info("Librarian started threads and waiting for tasks.")
            while run:
                try:
                    task = self.queue.get()
                    run = self._process_task(task)
                except Exception as exc:
                    self.log.error(f"Error in {self.__class__.__name__}")
                    self.log.exception(exc)
            self._stop_threads()
        except Exception as exc:
            self.log.error("Librarian crashed.")
            self.log.exception(exc)
        self.log.info("Stopped Librarian process.")

    def shutdown(self):
        """Send the shutdown gracefully task."""
        self.log.debug(f"{self.__class__.__name__} shutting down...")
        LIBRARIAN_QUEUE.put(self.SHUTDOWN_TASK)
        # LIBRARIAN_QUEUE.close()
        self.join(8)
        self.close()
        self.log.info(f"{self.__class__.__name__} stopped.")
