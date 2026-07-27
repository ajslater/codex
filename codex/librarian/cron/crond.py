"""Perform maintenance tasks."""

from collections.abc import Callable
from datetime import datetime
from threading import Condition, Event
from types import MappingProxyType
from typing import NamedTuple, override

from django.db import connections
from django.utils import timezone as django_timezone
from loguru._logger import Logger

from codex.librarian.scribe.janitor.scheduled_time import get_janitor_time
from codex.librarian.scribe.janitor.tasks import JanitorNightlyTask
from codex.librarian.telemeter.scheduled_time import (
    get_telemeter_time,
    mark_telemeter_attempt,
)
from codex.librarian.telemeter.tasks import TelemeterTask
from codex.librarian.threads import NamedThread


class _CronJob(NamedTuple):
    """When a recurring task runs next, and how to spend the slot it runs in."""

    get_time: Callable[[Logger], datetime | None]
    # Called just before the task is queued, for jobs whose next time is
    # read back out of state the job itself writes. ``None`` for jobs
    # whose schedule is pure clock arithmetic and so advances on its own.
    claim: Callable[[], None] | None = None


_CRON_JOBS: MappingProxyType[type, _CronJob] = MappingProxyType(
    {
        # Always the next midnight, so queueing it moves the schedule.
        JanitorNightlyTask: _CronJob(get_janitor_time),
        # Read out of the telemeter Timestamp, which the send writes on a
        # thread this one never joins. See ``mark_telemeter_attempt``.
        TelemeterTask: _CronJob(get_telemeter_time, mark_telemeter_attempt),
    }
)


class CronThread(NamedThread):
    """Run nightly cleanups."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize this thread with the worker."""
        self._stop_event = Event()
        self._cond = Condition()
        self._task_times = ()
        super().__init__(*args, daemon=True, **kwargs)

    def _create_task_times(self) -> None:
        task_times = {}
        for task_class, job in _CRON_JOBS.items():
            if dttm := job.get_time(self.log):
                task_times[dttm] = task_class

        self._task_times = tuple(sorted(task_times.items()))

    def _get_timeout(self) -> int:
        if not self._task_times or not self._task_times[0]:
            self.log.warning("No scheduled jobs found. Not normal! Waiting a minute.")
            return 60

        next_time = self._task_times[0][0]
        now = django_timezone.now()
        delta = next_time - now
        self.log.debug(f"Next scheduled job at {next_time} in {delta}.")
        return max(0, int(delta.total_seconds()))

    def _enqueue_job(self, task_class: type) -> None:
        """Spend the job's slot before queueing it, never after."""
        claim = _CRON_JOBS[task_class].claim
        if claim is not None:
            claim()
        self.librarian_queue.put(task_class())

    def _run_expired_jobs(self, *, timed_out: bool) -> None:
        """
        Queue every job whose scheduled time has arrived.

        ``timed_out`` means the wait ran its full course instead of being
        cut short by ``end_timeout``, so the job at the head of the
        schedule is due even if the clock reads a hair short of its time
        — ``_get_timeout`` truncates the delta to whole seconds, so the
        wait always ends slightly early. Missing that job cost more than
        a late run: ``_create_task_times`` would immediately push the
        nightly janitor out to the *following* midnight and skip a night.
        That is what ``sleep(2)  # fix time rounding problems`` was for.
        """
        now = django_timezone.now()
        if timed_out and self._task_times:
            now = max(now, self._task_times[0][0])
        for dttm, task_class in self._task_times:
            if dttm > now:
                # Times are always ordered so stop checking at the first future job.
                break
            self._enqueue_job(task_class)

    @override
    def run(self) -> None:
        """Cron loop."""
        try:
            self.run_start()
            with self._cond:
                self._create_task_times()
                while not self._stop_event.is_set():
                    timeout = self._get_timeout()
                    # Idle gaps between scheduled tasks are typically
                    # hours-to-days. Release the conn so the next
                    # ``cond.wait`` doesn't pin a file handle + a few
                    # tens of KiB of in-process state through that
                    # whole window. Reopen on the next query is
                    # ~5-20 ms, invisible against the wait.
                    connections.close_all()
                    # ``Condition.wait`` returns False only when the whole
                    # timeout elapsed; True means ``end_timeout`` notified.
                    timed_out = not self._cond.wait(timeout=timeout)
                    if self._stop_event.is_set():
                        break
                    self._run_expired_jobs(timed_out=timed_out)
                    # Recompute *after* queueing, so the new schedule sees
                    # the slots those jobs just claimed. Recomputing first
                    # re-read the telemeter's unchanged send time and put
                    # the same task on the queue again, once per pass, for
                    # as long as the offloaded send took to finish.
                    self._create_task_times()
        except Exception:
            self.log.exception(f"In {self.__class__.__name__}")
        self.log.debug(f"Stopped {self.__class__.__name__}.")

    def end_timeout(self) -> None:
        """End the timeout wait."""
        with self._cond:
            self._cond.notify()

    @override
    def stop(self) -> None:
        """Stop the cron thread."""
        super().stop()
        self._stop_event.set()
        self.end_timeout()
