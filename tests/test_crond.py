"""
Cron scheduling invariants.

:class:`CronThread` queues due jobs and *then* recomputes the schedule.
For the telemeter that schedule lives in the database and is written by
the send itself, which ``BookmarkThread`` runs on a daemon thread nobody
joins — so the recompute has to see a slot the scheduler spent, not one
the send has not gotten around to writing yet.
"""

from __future__ import annotations

from datetime import timedelta
from queue import SimpleQueue
from threading import Lock
from typing import TYPE_CHECKING
from uuid import UUID

from django.test import TestCase
from django.utils import timezone
from loguru import logger as _loguru_logger

from codex.choices.admin import AdminFlagChoices
from codex.librarian.cron.crond import CronThread
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
    """
    One trip around the cron loop, minus the wait.

    ``timed_out=True`` is the worst case for the job at the head of the
    schedule: it is the value the loop uses when it has waited out the
    full timeout, so nothing about a short clock reading can excuse a
    second enqueue.
    """
    thread._run_expired_jobs(timed_out=True)  # noqa: SLF001
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
    """Which jobs a wakeup is allowed to run."""

    @staticmethod
    def _janitor_a_moment_out() -> tuple[CronThread, SimpleQueue]:
        """Put the nightly janitor just past the clock, as truncation does."""
        thread, queue = _new_cron_thread()
        soon = timezone.now() + timedelta(milliseconds=500)
        thread._task_times = ((soon, JanitorNightlyTask),)  # noqa: SLF001
        return thread, queue

    def test_a_full_timeout_runs_the_job_it_waited_for(self) -> None:
        """
        ``_get_timeout`` truncates to whole seconds, so the wait ends early.

        Declining the job then would let ``_create_task_times`` push the
        nightly janitor out to the following midnight and skip a night.
        """
        thread, queue = self._janitor_a_moment_out()
        thread._run_expired_jobs(timed_out=True)  # noqa: SLF001
        assert not queue.empty()
        assert isinstance(queue.get_nowait(), JanitorNightlyTask)

    def test_being_woken_early_runs_nothing_early(self) -> None:
        """``end_timeout`` is a nudge to reschedule, not a licence to run."""
        thread, queue = self._janitor_a_moment_out()
        thread._run_expired_jobs(timed_out=False)  # noqa: SLF001
        assert queue.empty()


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
