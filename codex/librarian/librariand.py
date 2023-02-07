"""Library process worker for background tasks."""
import logging
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
from codex.librarian.notifier.notifierd import NotifierThread
from codex.librarian.notifier.tasks import NotifierTask
from codex.librarian.queue_mp import DelayedTasks
from codex.librarian.search.searchd import SearchIndexer
from codex.librarian.search.tasks import (
    SearchIndexerTask,
    SearchIndexRebuildIfDBChangedTask,
)
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
from codex.settings.logging import get_logger


class LibrarianDaemon(Process):
    """Librarian Process."""

    NAME = "Librarian"
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
        super().__init__(name=self.NAME, daemon=False)
        self.queue = queue
        self.log_queue = log_queue
        self.logger = get_logger(self.NAME, log_queue)

        logging.info("EXPERIMENTAL LOGGING MESSAGE")
        self.logger.info("EXPERIMENTAL LOGGER MESSAGE")

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
        print(task)
        if isinstance(task, CoverTask):
            self._threads["cover_creator"].queue.put(task)
        elif isinstance(task, WatchdogEventTask):
            self._threads["event_batcher"].queue.put(task)
        elif isinstance(task, UpdaterTask):
            self._threads["updater"].queue.put(task)
        elif isinstance(task, NotifierTask):
            self._threads["notifier"].queue.put(task)
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
            self._threads["delayed_tasks"].queue.put(task)
        elif task == self.SHUTDOWN_TASK:
            self.logger.info("Shutting down Librarian...")
            run = False
        else:
            self.logger.warning(f"Unhandled Librarian task: {task}")
        return run

    def _create_threads(self):
        """Create all the threads."""
        self.logger.debug("Creating Librarian threads...")
        self.logger.debug(f"Active threads before thread creation: {active_count()}")
        self._threads = {}
        kwargs = {"librarian_queue": self.queue, "log_queue": self.log_queue}
        for thread_class in self.THREAD_CLASSES:
            thread = thread_class(**kwargs)
            name = self._camel_to_snake_case(thread_class.__name__)
            self._threads[name] = thread
            self.logger.debug(f"Created {thread_class.__name__} thread.")
        self._observers = (
            self._threads["library_event_observer"],
            self._threads["library_polling_observer"],
        )
        self.logger.debug("Threads created")

    def _start_threads(self):
        """Start all librarian's threads."""
        self.logger.debug(f"Starting all {self.NAME} threads.")
        for thread in self._threads.values():
            thread.start()
        self.logger.info(f"Started all {self.NAME} threads.")

    def _stop_threads(self):
        """Stop all librarian's threads."""
        self.logger.debug(f"Stopping all {self.NAME} threads...")
        reversed_threads = reversed(self._threads.values())
        for thread in reversed_threads:
            thread.stop()
        for thread in reversed_threads:
            thread.join()
        self.logger.info(f"Joined all {self.NAME} threads.")

    def run(self):
        """
        Process tasks from the queue.

        This process also runs the crond thread and the Watchdog Observer
        threads.
        """
        print("RUN LIBRARIAN")
        try:
            self.logger.debug("Started Librarian process.")
            self.janitor = Janitor(self.log_queue, self.queue)
            self._create_threads()  # can't do this in init.
            print("START LIBRRIAN THREADS NEXT")
            self._start_threads()
            run = True
            self.logger.info("Librarian started threads and waiting for tasks.")
            while run:
                try:
                    print("WAITING FOR TASK")
                    task = self.queue.get()
                    print(task)
                    run = self._process_task(task)
                except Exception as exc:
                    self.logger.error(f"Error in {self.NAME}")
                    self.logger.exception(exc)
            self._stop_threads()
        except Exception as exc:
            self.logger.error("Librarian crashed.")
            self.logger.exception(exc)
        self.logger.info("Stopped Librarian process.")
