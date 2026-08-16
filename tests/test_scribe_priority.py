"""
Scribe task-priority invariants.

Every janitor task the scribe dispatches reaches ``ScribeThread.put`` →
:func:`get_task_priority`, which looks the task type up in
``_SCRIBE_TASK_PRIORITY`` via ``tuple.index``. A handled task missing
from that tuple raises ``ValueError`` and kills the librarian loop.
"""

from __future__ import annotations

from codex.librarian.scribe.janitor.janitor import _JANITOR_METHOD_MAP, _NIGHTLY_TASKS
from codex.librarian.scribe.janitor.tasks import JanitorFolderRelationsCheckTask
from codex.librarian.scribe.priority import _SCRIBE_TASK_PRIORITY, get_task_priority
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
    priority, now = get_task_priority(JanitorFolderRelationsCheckTask())
    assert isinstance(priority, int)
    assert isinstance(now, float)
