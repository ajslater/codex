"""
What reaches the LibrarianStatus row, and when.

The row is what the admin drawer's status rail renders, so an update the
controller coalesces away is a rail that sits still. Progress ticks are
worth coalescing — the next one carries the same information plus more.
A state change is not: it *is* the information, so it forces its way out.
"""

from __future__ import annotations

from typing import override

from django.test import TestCase
from loguru import logger

from codex.librarian.onlinetag.status import OnlineLookupStatus
from codex.librarian.status_controller import StatusController
from codex.models.admin import LibrarianStatus
from codex.startup import init_librarian_statuses


class _FakeQueue:
    """Collect the notifier tasks the controller enqueues."""

    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


class StatusUpdateTests(TestCase):
    """StatusController.update coalescing and the fields it writes."""

    @override
    def setUp(self) -> None:
        init_librarian_statuses()
        self.queue = _FakeQueue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.controller = StatusController(logger, self.queue)  # pyright: ignore[reportUninitializedInstanceVariable, reportArgumentType]  # ty: ignore[invalid-argument-type]
        self.status = OnlineLookupStatus(complete=0, total=8)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.controller.start(self.status)

    def _row(self) -> LibrarianStatus:
        return LibrarianStatus.objects.get(status_type=OnlineLookupStatus.CODE)

    def test_a_progress_tick_inside_the_window_is_coalesced(self) -> None:
        """The whole point of the window: one write per burst of ticks."""
        self.status.complete = 1

        self.controller.update(self.status)

        assert self._row().complete == 0

    def test_a_forced_update_lands_inside_the_window(self) -> None:
        """A state change dropped into the window is lost, not deferred."""
        self.status.complete = 1
        self.status.subtitle = "looking up on metron"

        self.controller.update(self.status, force=True)

        row = self._row()
        assert row.complete == 1
        assert row.subtitle == "looking up on metron"

    def test_an_emptied_subtitle_clears_the_row(self) -> None:
        """
        A subtitle only ever set is a subtitle that outlives its phase.

        The rail would keep describing the task as rate limited long after
        the source came back, because a cleared subtitle was skipped as
        "nothing to write".
        """
        self.status.subtitle = "rate limited by comicvine"
        self.controller.update(self.status, force=True)
        assert self._row().subtitle == "rate limited by comicvine"

        self.status.subtitle = ""
        self.controller.update(self.status, force=True)

        assert self._row().subtitle == ""
