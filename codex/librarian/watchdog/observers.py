"""The Codex Library Watchdog Observer threads."""
from watchdog.observers import Observer
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT, BaseObserver

from codex.librarian.watchdog.emitter import DatabasePollingEmitter
from codex.librarian.watchdog.eventsd import CodexLibraryEventHandler
from codex.models import Library
from codex.settings.logging import get_logger


class UatuMixin(BaseObserver):
    """Watch over librarys from the blue area of the moon."""

    ENABLE_FIELD = ""

    def __init__(self, *args, **kwargs):
        """Initialize queues."""
        self.librarian_queue = kwargs.pop("librarian_queue")
        self.log_queue = kwargs.pop("log_queue")
        self.logger = get_logger(self.__class__.__name__, self.log_queue)
        super().__init__(*args, **kwargs)

    def _get_watch(self, path):
        """Find the watch by path."""
        for watch in self._watches:
            if watch.path == path:
                return watch

    def _sync_library_watch(self, library):
        """Start a library watching process."""
        watch = self._get_watch(library.path)
        is_enabled = getattr(library, self.ENABLE_FIELD)
        watching_log = f"watching library {library.path} with {self.ENABLE_FIELD}"
        if watch and is_enabled:
            self.logger.info(f"Already {watching_log}.")
            return
        elif not watch and not is_enabled:
            self.logger.debug(f"Not {watching_log}, disabled.")
            return
        elif watch and not is_enabled:
            self.unschedule(watch)
            self.logger.info(f"Stopped {watching_log}.")
            return

        # Set up the watch
        handler = CodexLibraryEventHandler(
            library, librarian_queue=self.librarian_queue, log_queue=self.log_queue
        )
        self.schedule(handler, library.path, recursive=True)
        self.logger.info(f"Started {watching_log}")

    def _unschedule_orphan_watches(self, paths):
        """Unschedule lost watches."""
        orphan_watches = set()
        for watch in self._watches:
            if watch.path not in paths:
                orphan_watches.add(watch)
        for watch in orphan_watches:
            self.unschedule(watch)
            self.logger.info(
                f"Stopped watching orphaned library {watch.path} "
                f"with {self.ENABLE_FIELD}"
            )

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
                    self.logger.warning(
                        f"Could not find {library.path} to watch. May be unmounted."
                    )
                except Exception as exc:
                    self.logger.exception(exc)
            self._unschedule_orphan_watches(library_paths)
        except Exception as exc:
            self.logger.error(f"Error in {self.__class__.__name__}")
            self.logger.exception(exc)

    def run(self, *args, **kwargs):
        """Set thread name on thread start."""
        super().run(*args, **kwargs)


# It would be best for Codex to have one observer with multiple emitters, but the
#     watchdog class structure doesn't work that way.


class LibraryEventObserver(UatuMixin, Observer):
    """Regular observer."""

    ENABLE_FIELD = "events"


class LibraryPollingObserver(UatuMixin):
    """An Observer that polls using the DatabasePollingEmitter."""

    ENABLE_FIELD = "poll"
    _SHUTDOWN_EVENT = (None, None)

    def __init__(self, *args, timeout=DEFAULT_OBSERVER_TIMEOUT, **kwargs):
        """Use the DatabasePollingEmitter."""
        super().__init__(
            *args, emitter_class=DatabasePollingEmitter, timeout=timeout, **kwargs
        )

    def poll(self, library_pks, force=False):
        """Poll each requested emitter."""
        try:
            paths = Library.objects.filter(pk__in=library_pks).values_list(
                "path", flat=True
            )

            for emitter in self.emitters:
                if emitter.watch.path in paths:
                    emitter.poll(force)
        except Exception as exc:
            self.logger.error(
                f"Error in {self.__class__.__name__}.poll({library_pks}, {force})"
            )
            self.logger.exception(exc)

    def on_thread_stop(self):
        """Put a dummy event on the queue that blocks forever."""
        # The global timeout is None because the emitters have their own
        # per watch timeout. This makes self.dispatch_events() block
        # forever on the queue. Sending it an event lets it check the
        # shutdown event next.
        self.event_queue.put(self._SHUTDOWN_EVENT)
        super().on_thread_stop()
