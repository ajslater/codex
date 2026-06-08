"""
Unit tests for ``TagWriter`` progress reporting.

comicbox's ``bulk_write`` runs writes on a thread pool and yields per-file
events in *completion* order, each carrying the file's *submission* index
(``event.index``). ``TagWriter`` must report a monotonically increasing
completion count rather than echoing ``event.index`` -- otherwise the status
counter oscillates up and down as out-of-order indices stream in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from comicbox.events import BatchFinished, BatchStarted, FileError, FileParsed

from codex.librarian.scribe.tag_writer import TagWriter

if TYPE_CHECKING:
    from codex.librarian.scribe.status import TagWriteStatus


def _double(stub: object) -> Any:
    """Pass a test double through the concretely-typed ``status_controller`` seam."""
    return stub


class _RecordingController:
    """StatusController stand-in that records each call's count and identity."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, int | None, int]] = []

    def start(self, status: TagWriteStatus, **_kwargs: Any) -> None:
        self.calls.append(("start", status.complete, status.total, id(status)))

    def update(self, status: TagWriteStatus, **_kwargs: Any) -> None:
        self.calls.append(("update", status.complete, status.total, id(status)))

    def finish(self, status: TagWriteStatus | None, **_kwargs: Any) -> None:
        complete = status.complete if status else None
        total = status.total if status else None
        self.calls.append(("finish", complete, total, id(status) if status else 0))

    def non_finish(self) -> list[tuple[str, int | None, int | None, int]]:
        """Every recorded call except the terminal ``finish``."""
        return [call for call in self.calls if call[0] != "finish"]

    def named(self, name: str) -> list[tuple[str, int | None, int | None, int]]:
        """Every recorded call matching ``name``."""
        return [call for call in self.calls if call[0] == name]


def _writer_with_recorder() -> tuple[TagWriter, _RecordingController]:
    """Build a TagWriter without the threading machinery, recording status calls."""
    writer = TagWriter.__new__(TagWriter)
    controller = _RecordingController()
    # ``_on_event`` only touches ``status_controller``; erase the fake
    # through the strictly-typed seam.
    writer.status_controller = _double(controller)
    return writer, controller


def test_progress_monotonic_under_out_of_order_completion() -> None:
    """Jumbled completion-order indices must not push the count backwards."""
    writer, controller = _writer_with_recorder()
    total = 5

    writer._on_event(BatchStarted(total=total))  # noqa: SLF001
    # comicbox emits in completion order, so submission indices arrive jumbled.
    for index in (3, 0, 4, 1, 2):
        writer._on_event(FileParsed(index=index, total=total))  # noqa: SLF001
    writer._on_event(BatchFinished(total=total, parsed=total))  # noqa: SLF001

    non_finish = controller.non_finish()
    progress = [complete for _, complete, _, _ in non_finish]
    # Strictly increasing despite the jumbled indices: the regression guard.
    # With the old ``status.complete = event.index`` this would read
    # [0, 3, 0, 4, 1, 2] -- up, down, up, down.
    assert progress == [0, 1, 2, 3, 4, 5]

    totals = {t for _, _, t, _ in non_finish}
    assert totals == {total}  # denominator stays constant

    # A single status instance for the whole batch keeps ``since_updated``
    # alive so StatusController's rate-limit can actually throttle.
    update_idents = {ident for _, _, _, ident in controller.named("update")}
    assert len(update_idents) == 1

    assert controller.calls[-1][0] == "finish"


def test_errored_files_still_advance_progress() -> None:
    """A file that errors still advances the bar so the count reaches ``total``."""
    writer, controller = _writer_with_recorder()
    total = 3

    writer._on_event(BatchStarted(total=total))  # noqa: SLF001
    writer._on_event(FileParsed(index=0, total=total))  # noqa: SLF001
    writer._on_event(FileError(index=1, total=total, error="boom"))  # noqa: SLF001
    writer._on_event(FileParsed(index=2, total=total))  # noqa: SLF001
    writer._on_event(BatchFinished(total=total, parsed=2, errored=1))  # noqa: SLF001

    final = [complete for _, complete, _, _ in controller.named("update")][-1]
    assert final == total
