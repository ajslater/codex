"""The Codex Library Watchdog Observer threads."""
from logging import getLogger

from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from codex.librarian.watchdog.emitter import DatabasePollingEmitter
from codex.librarian.watchdog.eventsd import CodexLibraryEventHandler
from codex.models import Library


LOG = getLogger(__name__)


class UatuMixin(BaseObserver):
    """Watch over librarys from the blue area of the moon."""

    ENABLE_FIELD = ""

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
        if not watch and not is_enabled:
            LOG.debug(f"Not {watching_log}, disabled.")
            return
        elif watch and not is_enabled:
            self.unschedule(watch)
            LOG.info(f"Stopped {watching_log}.")
            return
        elif watch and is_enabled:
            LOG.info(f"Already {watching_log}.")
            return

        # Set up the watch
        handler = CodexLibraryEventHandler(library)
        self.schedule(handler, library.path, recursive=True)
        LOG.info(f"Started {watching_log}")

    def _unschedule_orphan_watches(self, paths):
        """Unschedule lost watches."""
        orphan_watches = set()
        for watch in self._watches:
            if watch.path not in paths:
                orphan_watches.add(watch)
        for watch in orphan_watches:
            self.unschedule(watch)
            LOG.info(
                f"Stopped watching orphaned library {watch.path} "
                f"with {self.ENABLE_FIELD}"
            )

    def sync_library_watches(self):
        """Watch or unwatch all libraries according to the db."""
        libraries = Library.objects.all().only("pk", "path", self.ENABLE_FIELD)
        library_paths = set()
        for library in libraries:
            try:
                library_paths.add(library.path)
                self._sync_library_watch(library)
            except FileNotFoundError:
                LOG.warning(
                    f"Could not find {library.path} to watch. May be unmounted."
                )
            except Exception as exc:
                LOG.exception(exc)
        self._unschedule_orphan_watches(library_paths)


# It would be best for Codex to have one observer with multiple emitters, but the
#     watchdog class structure doesn't work that way.


class LibraryEventObserver(UatuMixin, Observer):
    """Regular observer."""

    ENABLE_FIELD = "events"

    pass


class LibraryPollingObserver(UatuMixin):
    """An Observer that polls using the DatabasePollingEmitter."""

    ENABLE_FIELD = "poll"
    SHUTDOWN_EVENT = (None, None)

    def __init__(self):
        """Use the DatabasePollingEmitter."""
        super().__init__(emitter_class=DatabasePollingEmitter, timeout=None)

    def poll(self, library_pks, force=False):
        """Poll each requested emitter."""
        paths = Library.objects.filter(pk__in=library_pks).values_list(
            "path", flat=True
        )

        for emitter in self.emitters:
            if emitter.watch.path in paths:
                emitter.poll(force)

    def on_thread_stop(self):
        """Put a dummy event on the queue that blocks forever."""
        # The global timeout is None because the emitters have their own
        # per watch timeout. This makes self.dispatch_events() block
        # forever on the queue. Sending it an event lets it check the
        # shutdown event next.
        self.event_queue.put(self.SHUTDOWN_EVENT)
        super().on_thread_stop()
