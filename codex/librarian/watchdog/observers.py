"""The Codex Library Watchdog Observer threads."""

from multiprocessing.queues import Queue

from typing_extensions import override
from watchdog.events import (
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import (
    DEFAULT_OBSERVER_TIMEOUT,
    BaseObserver,
    EventDispatcher,
    ObservedWatch,
)

from codex.librarian.watchdog.const import EVENT_FILTER, POLLING_EVENT_FILTER
from codex.librarian.watchdog.emitter import DatabasePollingEmitter
from codex.librarian.watchdog.handlers import (
    CodexCustomCoverEventHandler,
    CodexLibraryEventHandler,
)
from codex.librarian.worker import WorkerMixin
from codex.models import Library


class UatuObserver(WorkerMixin, BaseObserver):
    """Watch over libraries from the blue area of the moon."""

    ENABLE_FIELD: str = ""
    ALWAYS_WATCH: bool = False

    def _get_watch(self, path):
        """Find the watch by path."""
        for watch in self._watches:
            if watch.path == path:
                return watch
        return None

    def _sync_library_watch(self, library):
        """Start a library watching process."""
        watch = self._get_watch(library.path)
        is_enabled = self.ALWAYS_WATCH or getattr(library, self.ENABLE_FIELD, False)
        watching_log = f"watching library {library.path} with {self.ENABLE_FIELD}"
        if watch and is_enabled:
            self.log.info(f"Already {watching_log}.")
            return
        if not watch and not is_enabled:
            self.log.debug(f"Not {watching_log}, disabled.")
            return
        if watch and not is_enabled:
            self.unschedule(watch)
            self.log.info(f"Stopped {watching_log}.")
            return

        # Set up the watch
        handler_class = (
            CodexCustomCoverEventHandler
            if library.covers_only
            else CodexLibraryEventHandler
        )
        handler = handler_class(
            library.pk,
            logger_=self.log,
            librarian_queue=self.librarian_queue,
            db_write_lock=self.db_write_lock,
        )
        self.schedule(handler, library.path, recursive=True)
        self.log.info(f"Started {watching_log}")

    def _unschedule_orphan_watches(self, paths):
        """Unschedule lost watches."""
        orphan_watches = set()
        for watch in self._watches:
            if watch.path not in paths:
                orphan_watches.add(watch)
        for watch in orphan_watches:
            self.unschedule(watch)
            reason = (
                f"Stopped watching orphaned library {watch.path} "
                f"with {self.ENABLE_FIELD}"
            )
            self.log.info(reason)

    def sync_library_watches(self):
        """Watch or unwatch all libraries according to the db."""
        try:
            libraries = Library.objects.all().only("pk", "path", self.ENABLE_FIELD)
            library_paths = set()
            for library in libraries:
                try:
                    library_paths.add(library.path)
                    self._sync_library_watch(library)
                except FileNotFoundError:
                    self.log.warning(
                        f"Could not find {library.path} to watch. May be unmounted."
                    )
                except Exception:
                    self.log.exception(f"Sync library watch for {library.path}")
            self._unschedule_orphan_watches(library_paths)
        except Exception:
            self.log.exception(f"{self.__class__.__name__} sync library watches")

    def _add_emitter_for_watch(
        self, event_handler: FileSystemEventHandler, watch: ObservedWatch
    ):
        """If we don't have an emitter for this watch already, create it."""
        covers_only = isinstance(event_handler, CodexCustomCoverEventHandler)
        library_id = Library.objects.get(path=watch.path).pk
        emitter = DatabasePollingEmitter(
            event_queue=self.event_queue,
            watch=watch,
            timeout=self.timeout,
            logger_=self.log,
            librarian_queue=self.librarian_queue,
            covers_only=covers_only,
            library_id=library_id,
            db_write_lock=self.db_write_lock,
            event_filter=list(POLLING_EVENT_FILTER),
        )
        self._add_emitter(emitter)
        if self.is_alive():
            emitter.start()

    @override
    def schedule(
        self,
        event_handler: FileSystemEventHandler,
        path: str,
        *,
        event_filter: list[type[FileSystemEvent]] | None = None,
        **kwargs,
    ) -> ObservedWatch:
        """Override BaseObserver for Codex emitter class."""
        if self._emitter_class != DatabasePollingEmitter:
            return super().schedule(
                event_handler, path, event_filter=list(POLLING_EVENT_FILTER), **kwargs
            )
        with self._lock:
            watch = ObservedWatch(path, event_filter=list(EVENT_FILTER), **kwargs)
            self._add_handler_for_watch(event_handler, watch)
            if self._emitter_for_watch.get(watch) is None:
                self._add_emitter_for_watch(event_handler, watch)
            self._watches.add(watch)
        return watch


#########################
# Observer Architecture #
#########################
# It would be better if could have one observer per path with multiple emitters, but the
# watchdog Observers key ObservedWatches on paths with one emitter each.
# But Observers have only one emitter_class and I can't override the FileSystem Emitters
# because they're generated per platform and environment. So the only overridable
# Emitter is my own DatabasePollingEmitter.


class LibraryEventObserver(UatuObserver, Observer):  # pyright: ignore[reportGeneralTypeIssues, reportUntypedBaseClass], # ty: ignore[invalid-base]
    """Regular observer."""

    # Observer is a dynamically generated class by platform at runtime.
    # Which causes the above static typing warning

    ENABLE_FIELD: str = "events"

    def __init__(self, logger_, librarian_queue: Queue, db_write_lock, *args, **kwargs):
        """Initialize queues."""
        if db_write_lock is None:
            reason = "db_write_lock argument must be a Lock."
            raise ValueError(reason)
        self.init_worker(logger_, librarian_queue, db_write_lock)
        super().__init__(*args, **kwargs)


class LibraryPollingObserver(UatuObserver):
    """An Observer that polls using the DatabasePollingEmitter."""

    ENABLE_FIELD: str = "poll"
    ALWAYS_WATCH: bool = True  # In the emitter, timeout=None for forever

    def __init__(
        self,
        logger_,
        librarian_queue: Queue,
        db_write_lock,
        *args,
        timeout: float = DEFAULT_OBSERVER_TIMEOUT,
        **kwargs,
    ):
        """Use the DatabasePollingEmitter."""
        self.init_worker(logger_, librarian_queue, db_write_lock)
        super().__init__(
            emitter_class=DatabasePollingEmitter, timeout=timeout, **kwargs
        )

    def poll(self, library_pks, *, force: bool):
        """Poll each requested emitter."""
        try:
            qs = Library.objects.all()
            if library_pks:
                qs = qs.filter(pk__in=library_pks)
            paths = frozenset(qs.values_list("path", flat=True))

            for emitter in self.emitters:
                polling_emitter: DatabasePollingEmitter = emitter  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
                if emitter.watch.path in paths:
                    polling_emitter.poll(force=force)
        except Exception:
            self.log.exception(
                f"{self.__class__.__name__}.poll({library_pks}, {force})"
            )

    @override
    def on_thread_stop(self):
        """Put a dummy event on the queue that blocks forever."""
        # The global timeout is None because the emitters have their own
        # per watch timeout. This makes self.dispatch_events() block
        # forever on the queue. Sending it an event makes it check the
        # shutdown event next.
        self.event_queue.put(EventDispatcher.stop_event)  # self._SHUTDOWN_EVENT)
        super().on_thread_stop()
