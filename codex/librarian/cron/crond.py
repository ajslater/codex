"""Perform maintenance tasks."""

from threading import Condition, Event
from time import sleep
from types import MappingProxyType

from django.utils import timezone as django_timezone

from codex.librarian.janitor.tasks import JanitorNightlyTask
from codex.librarian.janitor.time import get_janitor_time
from codex.librarian.telemeter.tasks import TelemeterTask
from codex.librarian.telemeter.time import get_telemeter_time
from codex.threads import NamedThread

_TASK_TIME_FUNCTION_MAP = MappingProxyType(
    {
        JanitorNightlyTask: get_janitor_time,
        TelemeterTask: get_telemeter_time,
    }
)


class CronThread(NamedThread):
    """Run nightly cleanups."""

    def __init__(self, *args, **kwargs):
        """Initialize this thread with the worker."""
        self._stop_event = Event()
        self._cond = Condition()
        self._task_times = ()
        super().__init__(*args, name=self.__class__.__name__, daemon=True, **kwargs)

    def _create_task_times(self):
        task_times = {}
        for task_class, func in _TASK_TIME_FUNCTION_MAP.items():
            if dttm := func(self.log):
                task_times[dttm] = task_class

        self._task_times = tuple(sorted(task_times.items()))

    def _get_timeout(self):
        if not self._task_times or not self._task_times[0]:
            self.log.warning("No scheduled jobs found. Not normal! Waiting a minute.")
            return 60

        next_time = self._task_times[0][0]
        now = django_timezone.now()
        delta = next_time - now
        self.log.debug(f"Next scheduled job at {next_time} in {delta}.")
        return max(0, int(delta.total_seconds()))

    def _run_expired_jobs(self):
        now = django_timezone.now()
        for dttm, task_class in self._task_times:
            if dttm < now:
                self.librarian_queue.put(task_class())
            else:
                # Times are always ordered so stop checking at the first future job.
                break

    def run(self):
        """Cron loop."""
        try:
            self.run_start()
            with self._cond:
                while not self._stop_event.is_set():
                    self._run_expired_jobs()
                    self._create_task_times()
                    sleep(2)  # try to fix double jobs
                    timeout = self._get_timeout()
                    self._cond.wait(timeout=timeout)
                    if self._stop_event.is_set():
                        break
                    sleep(2)  # fix time rounding problems
        except Exception:
            self.log.exception(f"In {self.__class__.__name__}")
        self.log.debug(f"Stopped {self.__class__.__name__}.")

    def end_timeout(self):
        """End the timeout wait."""
        with self._cond:
            self._cond.notify()

    def stop(self):
        """Stop the cron thread."""
        self._stop_event.set()
        self.end_timeout()
