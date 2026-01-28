"""Library process worker for background tasks."""

from copy import copy
from multiprocessing import Process, Queue
from threading import Lock, active_count
from types import MappingProxyType
from typing import Any, NamedTuple

from aioprocessing.queues import AioQueue
from caseconverter import snakecase
from django.db import close_old_connections
from typing_extensions import override

from codex.librarian.bookmark.bookmarkd import BookmarkThread  # typos:ignore
from codex.librarian.bookmark.tasks import BookmarkTask
from codex.librarian.covers.coverd import (  # codespell:ignore coverd, typos:ignore
    CoverThread,
)
from codex.librarian.covers.tasks import CoverTask
from codex.librarian.cron.crond import CronThread
from codex.librarian.notifier.notifierd import NotifierThread
from codex.librarian.notifier.tasks import NotifierTask
from codex.librarian.restarter.restarter import CodexRestarter
from codex.librarian.restarter.tasks import CodexRestarterTask
from codex.librarian.scribe.janitor.tasks import JanitorAdoptOrphanFoldersTask
from codex.librarian.scribe.scribed import ScribeThread
from codex.librarian.scribe.search.tasks import SearchIndexSyncTask
from codex.librarian.scribe.tasks import ScribeTask
from codex.librarian.tasks import LibrarianShutdownTask, WakeCronTask
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

_THREAD_CLASSES = (
    BookmarkThread,
    CoverThread,
    CronThread,
    LibraryEventObserver,
    LibraryPollingObserver,
    NotifierThread,
    ScribeThread,
    WatchdogEventBatcherThread,
)
_THREAD_CLASS_MAP = MappingProxyType(
    {snakecase(thread_class.__name__): thread_class for thread_class in _THREAD_CLASSES}
)
LibrarianThreads = NamedTuple("LibrarianThreads", tuple(_THREAD_CLASS_MAP.items()))  # ty: ignore[invalid-named-tuple]


class LibrarianDaemon(Process):
    """Librarian Process."""

    def __init__(self, logger_, queue: Queue, broadcast_queue: AioQueue):
        """Init process."""
        self.log = logger_
        name = self.__class__.__name__
        super().__init__(name=name, daemon=False)
        self.queue = queue
        self.broadcast_queue = broadcast_queue
        startup_tasks = (
            JanitorAdoptOrphanFoldersTask(),
            WatchdogSyncTask(),
            SearchIndexSyncTask(),
        )

        for task in startup_tasks:
            self.queue.put(task)
        self.run_loop = True
        self._reversed_threads = ()

    def _process_task(self, task):  # noqa: C901
        """Process an individual task popped off the queue."""
        match task:
            case CoverTask():
                self._threads.cover_thread.queue.put(task)
            case BookmarkTask():
                self._threads.bookmark_thread.queue.put(task)
            case NotifierTask():
                self._threads.notifier_thread.queue.put(task)
            case WatchdogEventTask():
                self._threads.watchdog_event_batcher_thread.queue.put(task)
            case ScribeTask():
                self._threads.scribe_thread.put(task)
            case WatchdogSyncTask():
                for observer in self._observers:
                    observer.sync_library_watches()
            case WatchdogPollLibrariesTask():
                self._threads.library_polling_observer.poll(
                    task.library_ids, force=task.force
                )
            case WakeCronTask():
                self._threads.cron_thread.end_timeout()
            case CodexRestarterTask():
                restarter = CodexRestarter(self.log, self.queue, self.db_write_lock)
                restarter.handle_task(task)
            case LibrarianShutdownTask():
                self.log.info(f"Shutting down {self.name}...")
                self.run_loop = False
            case _:
                self.log.warning(f"Unhandled Librarian task: {task}")

    def _create_threads(self):
        """Create all the threads."""
        self.log.debug("Creating Librarian threads...")
        self.log.debug(f"Active threads before thread creation: {active_count()}")
        self.db_write_lock = Lock()  # pyright: ignore[reportUninitializedInstanceVariable]
        threads = {}
        kwargs: dict[str, Any] = {}
        for name, thread_class in _THREAD_CLASS_MAP.items():
            thread_kwargs = copy(kwargs)
            if thread_class == NotifierThread:
                thread_kwargs["broadcast_queue"] = self.broadcast_queue
            thread = thread_class(
                self.log, self.queue, self.db_write_lock, **thread_kwargs
            )
            threads[name] = thread
            self.log.debug(f"Created {name} thread.")
        self._threads = LibrarianThreads(**threads)  # pyright: ignore[reportUninitializedInstanceVariable]
        self._observers = (  # pyright: ignore[reportUninitializedInstanceVariable]
            self._threads.library_event_observer,
            self._threads.library_polling_observer,
        )
        self.log.debug("Threads created")

    def _start_threads(self):
        """Start all librarian's threads."""
        self.log.debug(f"{self.name} starting all threads.")
        for thread in self._threads:
            thread.start()
        self.log.info(f"{self.name} started all threads.")

    def _startup(self):
        """Initialize threads."""
        self.log.debug(f"Started {self.name}.")
        # Janitor created in init.
        self._create_threads()  # can't do this in init.
        self._start_threads()
        self.log.success(f"{self.name} ready for tasks.")

    def _stop_threads(self):
        """Stop all librarian's threads."""
        self.log.debug(f"{self.name} stopping all threads...")
        for thread in self._reversed_threads:
            thread.stop()
        self.log.debug(f"{self.name} stopped all threads.")

    def _join_threads(self):
        """Join all librarian threads."""
        self.log.debug(f"{self.name} joining all threads...")
        for thread in self._reversed_threads:
            thread.join()
        self.log.info(f"{self.name} joined all threads.")

    def _shutdown(self):
        """Shutdown threads and queues."""
        self._reversed_threads = tuple(reversed(self._threads))
        self._stop_threads()
        self._join_threads()
        while not self.queue.empty():
            self.queue.get_nowait()
        self.queue.close()
        self.queue.join_thread()
        self.log.success(f"{self.name} finished.")

    @override
    def run(self):
        """
        Process tasks from the queue.

        This process also runs the crond thread and the Watchdog Observer
        threads.
        """
        self._startup()
        try:
            while self.run_loop:
                try:
                    task = self.queue.get()
                    close_old_connections()
                    self._process_task(task)
                except Exception:
                    self.log.exception(f"In {self.name} loop")
        except Exception:
            self.log.exception(f"{self.name} crashed.")
        except KeyboardInterrupt:
            self.log.debug(f"{self.name} Keyboard interrupt")
        finally:
            self._shutdown()

    def stop(self):
        """Close up the librarian process."""
        self.queue.put(LibrarianShutdownTask())
        self.queue.close()
        self.queue.join_thread()
        self.join()
        self.close()
