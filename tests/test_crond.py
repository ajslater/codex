"""
Cron scheduling invariants.

:class:`CronThread` queues due jobs and *then* recomputes the schedule.
For the telemeter that schedule lives in the database and is written by
the send itself, which ``BookmarkThread`` runs on a daemon thread nobody
joins — so the recompute has to see a slot the scheduler spent, not one
the send has not gotten around to writing yet.

The other half is the clock: a job runs when the clock reaches its slot
and not a moment before. Firing early left the slot in the future for
the recompute that follows, which handed back a zero timeout and a wait
that returned at once — the whole night's work, queued again, on every
pass until the clock caught up.
"""

from __future__ import annotations

import time as time_module
from datetime import UTC, date, datetime, timedelta
from os import environ
from queue import SimpleQueue
from threading import Lock
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import UUID

import pytest
from django.test import TestCase
from django.utils import timezone
from loguru import logger as _loguru_logger

from codex.choices.admin import AdminFlagChoices
from codex.librarian.cron.crond import CronThread
from codex.librarian.scribe.janitor.scheduled_time import get_janitor_time
from codex.librarian.scribe.janitor.tasks import JanitorNightlyTask
from codex.librarian.telemeter.scheduled_time import (
    get_telemeter_time,
    mark_telemeter_attempt,
)
from codex.librarian.telemeter.tasks import TelemeterTask
from codex.librarian.telemeter.telemeter import get_telemeter_timestamp
from codex.models.admin import AdminFlag, Timestamp
from codex.startup import init_admin_flags

if TYPE_CHECKING:
    from loguru._logger import Logger

# The send time is the install uuid scaled across the week, so int=0 puts
# it at Monday 00:00 UTC — always in the past, so the job is always due.
_START_OF_WEEK_UUID = str(UUID(int=0))
_LONG_AGO = timedelta(days=30)
# Sub-second offsets from a slot. The waits these produce are exactly
# what whole-second truncation used to round away to nothing.
_A_MOMENT = timedelta(milliseconds=500)
_SHORT_OF_IT = timedelta(milliseconds=300)
_PAST_IT = timedelta(milliseconds=50)
# ``loguru.logger`` *is* a ``loguru._logger.Logger`` at runtime; loguru's
# stubs declare a second, unrelated ``loguru.Logger`` for the singleton,
# and that is not the type the librarian annotates its ``log`` params with.
_LOG: Logger = _loguru_logger  # pyright: ignore[reportAssignmentType]  # ty: ignore[invalid-assignment]


def _make_telemeter_overdue() -> Timestamp:
    """Make the telemeter look installed long ago and never sent."""
    init_admin_flags()
    AdminFlag.objects.filter(key=AdminFlagChoices.SEND_TELEMETRY.value).update(on=True)
    ts = get_telemeter_timestamp()
    long_ago = timezone.now() - _LONG_AGO
    # A queryset update writes the columns auto_now/auto_now_add own.
    Timestamp.objects.filter(pk=ts.pk).update(
        value=_START_OF_WEEK_UUID, created_at=long_ago, updated_at=long_ago
    )
    ts.refresh_from_db()
    return ts


def _new_cron_thread() -> tuple[CronThread, SimpleQueue]:
    """Build a cron thread wired to a queue the test can read, never started."""
    queue = SimpleQueue()
    return CronThread(_LOG, queue, Lock()), queue


def _drain(queue: SimpleQueue) -> list:
    """Everything the loop put on the librarian queue."""
    tasks = []
    while not queue.empty():
        tasks.append(queue.get_nowait())
    return tasks


def _cron_pass(thread: CronThread) -> None:
    """One trip around the cron loop, minus the wait."""
    thread._run_expired_jobs()  # noqa: SLF001
    thread._create_task_times()  # noqa: SLF001


def _scheduled_classes(thread: CronThread) -> set[type]:
    """Collect the task classes on the thread's current schedule."""
    return {task_class for _, task_class in thread._task_times}  # noqa: SLF001


class CronScheduleTestCase(TestCase):
    """The loop must queue an overdue job exactly once."""

    def _start(self) -> tuple[CronThread, SimpleQueue]:
        """Prime a cron thread on an overdue telemeter, the way ``run`` primes it."""
        _make_telemeter_overdue()
        thread, queue = _new_cron_thread()
        thread._create_task_times()  # noqa: SLF001
        return thread, queue

    def test_telemeter_is_queued_once_while_the_send_is_in_flight(self) -> None:
        """
        The reported bug: three passes, no send, one task.

        Never calling ``send_telemetry`` is the point — it stands in for
        the offloaded send still collecting counts or blocked on its five
        second network timeout, having written nothing back yet.
        """
        thread, queue = self._start()
        for _ in range(3):
            _cron_pass(thread)
        queued = [task for task in _drain(queue) if isinstance(task, TelemeterTask)]
        assert len(queued) == 1, (
            f"Queued {len(queued)} TelemeterTasks; the send never ran, so the "
            "loop re-read an unclaimed send time and enqueued it again."
        )

    def test_queueing_the_telemeter_takes_it_off_the_schedule(self) -> None:
        """A claimed slot must be gone from the very next recompute."""
        thread, _ = self._start()
        assert TelemeterTask in _scheduled_classes(thread)
        _cron_pass(thread)
        assert TelemeterTask not in _scheduled_classes(thread)
        # Not merely absent from the tuple — unschedulable at the source,
        # which is what keeps ``_get_timeout`` off zero and the loop from
        # spinning.
        assert get_telemeter_time(_LOG) is None

    def test_next_week_is_scheduled_again(self) -> None:
        """Spending this week's slot must not retire the job."""
        thread, _ = self._start()
        _cron_pass(thread)
        assert get_telemeter_time(_LOG) is None
        # Age the claim past the start of this week: the slot moves with
        # the calendar, the claim does not.
        Timestamp.objects.filter(key=Timestamp.Choices.TELEMETER_SENT.value).update(
            updated_at=timezone.now() - timedelta(days=8)
        )
        assert get_telemeter_time(_LOG) is not None


class CronWakeupTestCase(TestCase):
    """What a wakeup short of the next slot is allowed to do."""

    @staticmethod
    def _janitor_a_moment_out() -> tuple[CronThread, SimpleQueue]:
        """Put the nightly janitor half a second ahead of the clock."""
        thread, queue = _new_cron_thread()
        soon = timezone.now() + _A_MOMENT
        thread._task_times = ((soon, JanitorNightlyTask),)  # noqa: SLF001
        return thread, queue

    def test_a_slot_still_ahead_of_the_clock_is_not_run(self) -> None:
        """Whatever ended the wait, the clock decides what runs."""
        thread, queue = self._janitor_a_moment_out()
        thread._run_expired_jobs()  # noqa: SLF001
        assert queue.empty()

    def test_a_sub_second_wait_is_not_rounded_to_nothing(self) -> None:
        """
        The remainder is what the loop waits out, so it has to survive.

        Truncating it to whole seconds made every wait end early and the
        one that followed return at once.
        """
        thread, _ = self._janitor_a_moment_out()
        timeout = thread._get_timeout()  # noqa: SLF001
        assert 0 < timeout <= _A_MOMENT.total_seconds()


class CronEarlyWakeTestCase(TestCase):
    """A wakeup a hair short of the slot must not spend the slot."""

    @staticmethod
    def _only_the_janitor() -> None:
        """Leave the nightly janitor as the one scheduled job."""
        init_admin_flags()
        AdminFlag.objects.filter(key=AdminFlagChoices.SEND_TELEMETRY.value).update(
            on=False
        )

    @staticmethod
    def _passes_short_of_midnight(
        thread: CronThread, queue: SimpleQueue, midnight: datetime
    ) -> None:
        """Three passes with the clock a hair short of the slot."""
        with patch("django.utils.timezone.now", return_value=midnight - _SHORT_OF_IT):
            thread._create_task_times()  # noqa: SLF001
            assert thread._task_times == ((midnight, JanitorNightlyTask),)  # noqa: SLF001
            for _ in range(3):
                _cron_pass(thread)
            assert queue.empty(), (
                f"Queued {len(_drain(queue))} tasks before midnight; the slot "
                "had not arrived on any of those passes."
            )
            # Still scheduled, and the loop has the remainder to wait out
            # rather than a timeout of zero.
            assert _scheduled_classes(thread) == {JanitorNightlyTask}
            assert 0 < thread._get_timeout() <= _SHORT_OF_IT.total_seconds()  # noqa: SLF001

    @staticmethod
    def _passes_past_midnight(thread: CronThread, midnight: datetime) -> None:
        """Three more with the slot behind the clock."""
        with patch("django.utils.timezone.now", return_value=midnight + _PAST_IT):
            for _ in range(3):
                _cron_pass(thread)
            # The recompute moved on: tonight's slot is spent for good.
            assert thread._task_times[0][0] > midnight  # noqa: SLF001

    def test_the_nightly_janitor_runs_once_across_an_early_wake(self) -> None:
        """
        The reported bug: dozens of nightly runs, every night.

        A wait timed on the monotonic clock can end with the wall clock
        reading a hair short of midnight. Queueing the night's work then
        left ``_create_task_times`` recomputing the very same midnight,
        a zero timeout, and a wait that returned at once — so the work
        was queued again on every pass until the clock caught up.
        """
        self._only_the_janitor()
        # Both this module and the janitor read ``now`` off
        # ``django.utils.timezone`` at call time, so one patch freezes both.
        midnight = get_janitor_time(_LOG)
        thread, queue = _new_cron_thread()

        self._passes_short_of_midnight(thread, queue, midnight)
        self._passes_past_midnight(thread, midnight)

        queued = [
            task for task in _drain(queue) if isinstance(task, JanitorNightlyTask)
        ]
        assert len(queued) == 1, (
            f"Queued {len(queued)} JanitorNightlyTasks for one midnight; each "
            "one runs the whole night's janitor work."
        )


class JanitorTimeTestCase(TestCase):
    """The nightly slot is a calendar midnight, not a day of seconds."""

    # 00:30 Pacific on the night daylight saving time ends, when the
    # local day is 25 hours long.
    _DST_END_MORNING = datetime(2026, 11, 1, 7, 30, tzinfo=UTC)

    @staticmethod
    def _pacific() -> None:
        """Point the local clock at a zone that changes offset that night."""
        environ["TZ"] = "America/Los_Angeles"
        time_module.tzset()

    @pytest.mark.skipif(not hasattr(time_module, "tzset"), reason="tzset is POSIX only")
    def test_the_next_midnight_is_the_calendar_day_after(self) -> None:
        """
        Adding 24 hours lands on the same date when the day is 25 hours long.

        That handed back the midnight that had just fired — a slot in the
        past, and an hour of it.
        """
        old_tz = environ.get("TZ")
        try:
            self._pacific()
            with patch("django.utils.timezone.now", return_value=self._DST_END_MORNING):
                dttm = get_janitor_time(_LOG)
            assert dttm > self._DST_END_MORNING
            assert dttm.astimezone().date() == date(2026, 11, 2)
        finally:
            if old_tz is None:
                environ.pop("TZ", None)
            else:
                environ["TZ"] = old_tz
            time_module.tzset()


class TelemeterScheduleTestCase(TestCase):
    """What ``get_telemeter_time`` will and will not schedule."""

    def test_an_overdue_send_is_scheduled_in_the_past(self) -> None:
        """A missed slot stays due rather than rolling over."""
        _make_telemeter_overdue()
        dttm = get_telemeter_time(_LOG)
        assert dttm is not None
        assert dttm <= timezone.now()

    def test_disabled_telemetry_is_not_scheduled(self) -> None:
        """The admin flag is checked before anything else."""
        _make_telemeter_overdue()
        AdminFlag.objects.filter(key=AdminFlagChoices.SEND_TELEMETRY.value).update(
            on=False
        )
        assert get_telemeter_time(_LOG) is None

    def test_a_fresh_install_waits_a_day(self) -> None:
        """New installs don't report on their first day."""
        ts = _make_telemeter_overdue()
        Timestamp.objects.filter(pk=ts.pk).update(created_at=timezone.now())
        assert get_telemeter_time(_LOG) is None

    def test_claiming_the_slot_unschedules_it(self) -> None:
        """The unit the cron thread relies on, independent of the loop."""
        _make_telemeter_overdue()
        assert get_telemeter_time(_LOG) is not None
        mark_telemeter_attempt()
        assert get_telemeter_time(_LOG) is None
