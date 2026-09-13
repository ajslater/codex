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
        # Pure clock arithmetic: the next midnight after now. The clock
        # moves the schedule along, not the queueing, so the job must not
        # run until the clock has actually reached the slot.
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
        self._task_times: tuple[tuple[datetime, type], ...] = ()
        super().__init__(*args, daemon=True, **kwargs)

    def _create_task_times(self) -> None:
        task_times = {}
        for task_class, job in _CRON_JOBS.items():
            if dttm := job.get_time(self.log):
                task_times[dttm] = task_class

        self._task_times = tuple(sorted(task_times.items()))

    def _get_timeout(self) -> float:
        if not self._task_times:
            self.log.warning("No scheduled jobs found. Not normal! Waiting a minute.")
            return 60.0

        next_time = self._task_times[0][0]
        now = django_timezone.now()
        delta = next_time - now
        self.log.debug(f"Next scheduled job at {next_time} in {delta}.")
        # The sub-second remainder is the whole point of this number.
        # Truncating it to whole seconds ended every wait early, and then
        # the wait for the leftover fraction was a wait of zero, which
        # returns at once. ``Condition.wait`` rejects a negative timeout,
        # so a slot already in the past clamps to no wait at all.
        return max(0.0, delta.total_seconds())

    def _enqueue_job(self, task_class: type) -> None:
        """Spend the job's slot before queueing it, never after."""
        claim = _CRON_JOBS[task_class].claim
        if claim is not None:
            claim()
        self.librarian_queue.put(task_class())

    def _run_expired_jobs(self) -> None:
        """
        Queue every job whose scheduled time has arrived, and no others.

        The clock is the only authority on that. A wait can end short of
        the slot it waited for — it is timed on the monotonic clock while
        the slot is wall time, and NTP slews the two apart — and running
        the job anyway does not skip the wait, it repeats it: the jobs
        recompute their next time off the same short clock and hand back
        the slot just run, ``_get_timeout`` returns the remainder, and
        the whole night's work goes on the queue again on every pass
        until the clock catches up. Declining costs one more trip around
        the loop, waiting out a remainder measured in milliseconds.
        """
        now = django_timezone.now()
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
                    # ~1 ms, invisible against the wait.
                    connections.close_all()
                    # Whether the wait ran its course or ``end_timeout``
                    # cut it short makes no difference to what is due;
                    # ``_run_expired_jobs`` asks the clock either way.
                    self._cond.wait(timeout=timeout)
                    if self._stop_event.is_set():
                        break
                    self._run_expired_jobs()
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
