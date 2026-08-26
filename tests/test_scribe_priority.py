"""
Scribe task-priority invariants.

Every janitor task the scribe dispatches reaches ``ScribeThread.put`` →
:func:`get_task_priority`, which looks the task type up in
``_SCRIBE_TASK_PRIORITY`` via ``tuple.index``. A handled task missing
from that tuple raises ``ValueError`` and kills the librarian loop.
"""

from __future__ import annotations

from queue import PriorityQueue
from unittest.mock import patch

from codex.librarian.scribe.importer.tasks import ImportTask
from codex.librarian.scribe.janitor.janitor import _JANITOR_METHOD_MAP, _NIGHTLY_TASKS
from codex.librarian.scribe.janitor.tasks import JanitorFolderRelationsCheckTask
from codex.librarian.scribe.priority import _SCRIBE_TASK_PRIORITY, get_task_priority
from codex.librarian.scribe.scribed import ScribeThread
from codex.librarian.scribe.tasks import ScribeTask


def test_scribe_janitor_tasks_are_priority_rankable() -> None:
    """Every janitor task the scribe handles must be in _SCRIBE_TASK_PRIORITY."""
    missing = sorted(
        cls.__name__ for cls in _JANITOR_METHOD_MAP if cls not in _SCRIBE_TASK_PRIORITY
    )
    assert not missing, (
        "Janitor tasks dispatched by the scribe but absent from "
        f"_SCRIBE_TASK_PRIORITY (get_task_priority would raise): {missing}"
    )


def test_nightly_scribe_tasks_are_priority_rankable() -> None:
    """The nightly fan-out queues scribe tasks, which must all be rankable."""
    missing = sorted(
        type(task).__name__
        for task in _NIGHTLY_TASKS
        if isinstance(task, ScribeTask) and type(task) not in _SCRIBE_TASK_PRIORITY
    )
    assert not missing, (
        "Nightly scribe tasks absent from _SCRIBE_TASK_PRIORITY "
        f"(get_task_priority would raise): {missing}"
    )


def test_get_task_priority_folder_relations_check() -> None:
    """The reported crash: ranking JanitorFolderRelationsCheckTask must not raise."""
    priority, now, tie_breaker = get_task_priority(JanitorFolderRelationsCheckTask())
    assert isinstance(priority, int)
    assert isinstance(now, float)
    assert isinstance(tie_breaker, int)


def test_equal_priorities_never_compare_tasks() -> None:
    """
    Two same-class tasks must be orderable even with an identical timestamp.

    Without a tie-breaker the heap falls through to comparing the tasks
    themselves, and ScribeTask dataclasses define no ordering — the push
    raises TypeError in the routing thread and the task is lost.
    """
    frozen = 1724500000.0
    with patch("codex.librarian.scribe.priority.datetime") as mock_datetime:
        mock_datetime.now.return_value.timestamp.return_value = frozen
        first = get_task_priority(ImportTask(library_id=1))
        second = get_task_priority(ImportTask(library_id=1))

    assert first[:2] == second[:2], "timestamps should be identical for this test"
    queue = PriorityQueue()
    queue.put((first, ImportTask(library_id=1)))
    queue.put((second, ImportTask(library_id=1)))
    assert queue.get()[0] == first
    assert queue.get()[0] == second


def test_shutdown_msg_orders_against_a_pending_task() -> None:
    """Stopping the thread with work queued must not raise TypeError."""
    queue = PriorityQueue()
    queue.put((get_task_priority(ImportTask(library_id=1)), ImportTask(library_id=1)))
    queue.put(ScribeThread.SHUTDOWN_MSG)
    # Shutdown outranks queued work, and its shape still round-trips equality.
    assert queue.get() == ScribeThread.SHUTDOWN_MSG
