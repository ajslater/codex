"""Perform maintence tasks."""
from datetime import datetime, time, timedelta
from threading import Condition, Event
from time import sleep

from django.utils import timezone as django_timezone
from humanize import naturaldelta

from codex.librarian.janitor.tasks import JanitorNightlyTask
from codex.models import Timestamp
from codex.threads import NamedThread

_ONE_DAY = timedelta(days=1)


class JanitorThread(NamedThread):
    """Run nightly cleanups."""

    @staticmethod
    def _get_midnight(now, tomorrow=False):
        """Get midnight relative to now."""
        if tomorrow:
            now += _ONE_DAY
        day = now.astimezone()
        return datetime.combine(day, time.min).astimezone()

    @classmethod
    def _get_timeout(cls):
        """Get seconds until midnight."""
        now = django_timezone.now()
        last_cron = Timestamp.objects.get(
            key=Timestamp.TimestampChoices.JANITOR.value
        ).updated_at

        if now - last_cron < _ONE_DAY:
            # wait until next midnight
            next_midnight = cls._get_midnight(now, True)
            delta = next_midnight - now
            seconds = max(0, int(delta.total_seconds()))
        else:
            # it's been too long
            seconds = 0

        return seconds

    def __init__(self, *args, **kwargs):
        """Initialize this thread with the worker."""
        self._stop_event = Event()
        self._cond = Condition()
        super().__init__(*args, name=self.__class__.__name__, daemon=True, **kwargs)

    def run(self):
        """Watch a path and log the events."""
        try:
            self.run_start()
            with self._cond:
                while not self._stop_event.is_set():
                    timeout = self._get_timeout()
                    self.log.info(
                        f"Waiting {naturaldelta(timeout)} until next maintenance."
                    )
                    self._cond.wait(timeout=timeout)
                    if self._stop_event.is_set():
                        break
                    self.librarian_queue.put(JanitorNightlyTask())
                    sleep(2)
        except Exception:
            self.log.exception(f"In {self.__class__.__name__}")
        self.log.debug(f"Stopped {self.__class__.__name__}.")

    def stop(self):
        """Stop the cron thread."""
        self._stop_event.set()
        with self._cond:
            self._cond.notify()
