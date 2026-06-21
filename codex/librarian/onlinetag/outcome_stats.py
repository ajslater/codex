"""
Per-session outcome counters for an online tagging scan.

Folded from the comicbox event stream (one :meth:`record` call per event)
so the manager can log an end-of-session summary like::

    Online tag session finished in 14 seconds: 17 comics — matched 12
    (comicvine 4, metron 8), 3 skipped, 2 deferred for manual prompts.

The per-comic anchor is :class:`~comicbox.events.FileFinished`, emitted
exactly once per comic with ``outcome="written"`` (a source matched and
tags were written) or ``"no_change"`` (nothing matched).
:class:`~comicbox.events.AutoWritten` attributes a matched comic to the
source that won it; comics refreshed from a stored id win without an
``AutoWritten`` event, so the per-source tallies can sum to fewer than the
matched total — the remainder is reported as "refreshed from stored id".
:class:`~comicbox.events.PromptDeferred` marks comics queued for manual
resolution; :class:`~comicbox.events.FileError` marks comics that raised
before finishing.

One scan runs on a single daemon thread and emits its events inline, so the
tallies need no locking.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from comicbox.events import AutoWritten, FileError, FileFinished, PromptDeferred

if TYPE_CHECKING:
    from pathlib import Path

    from comicbox.events import Event


@dataclass
class OnlineTagOutcomeStats:
    """Accumulate per-comic online-tagging outcomes for an end-of-session summary."""

    matched_source_by_path: dict[Path, list[str]] = field(default_factory=dict)
    written_paths: set[Path] = field(default_factory=set)
    no_change_paths: set[Path] = field(default_factory=set)
    deferred_paths: set[Path] = field(default_factory=set)
    errored_paths: set[Path] = field(default_factory=set)

    def record(self, event: Event) -> None:
        """Fold one comicbox event into the running tallies."""
        match event:
            case AutoWritten(path=path, source=source) if path and source:
                # Under merge_all_sources a comic can be auto-written by more
                # than one source, so accumulate (deduped, order preserved)
                # rather than letting the last event clobber the first.
                sources = self.matched_source_by_path.setdefault(path, [])
                if source not in sources:
                    sources.append(source)
            case FileFinished(path=path, outcome=outcome) if path:
                bucket = (
                    self.written_paths if outcome == "written" else self.no_change_paths
                )
                bucket.add(path)
            case PromptDeferred(path=path) if path:
                self.deferred_paths.add(path)
            case FileError(path=path) if path:
                self.errored_paths.add(path)
            case _:
                pass

    @property
    def matched(self) -> int:
        """Comics that a source matched and wrote tags to."""
        return len(self.written_paths)

    @property
    def deferred(self) -> int:
        """
        Unmatched comics queued for a manual prompt.

        A matched comic that incidentally deferred a *different* source's
        prompt is counted as matched, not deferred — hence the intersection
        with the unmatched set.
        """
        return len(self.deferred_paths & self.no_change_paths)

    @property
    def skipped(self) -> int:
        """Unmatched comics that were not deferred for a prompt."""
        return len(self.no_change_paths) - self.deferred

    @property
    def errored(self) -> int:
        """Comics that raised before finishing."""
        return len(self.errored_paths)

    @property
    def total(self) -> int:
        """Comics that produced any outcome this session."""
        return self.matched + len(self.no_change_paths) + self.errored

    def _source_breakdown(self) -> str:
        """Render the per-source match tally, e.g. ``comicvine 4, metron 8``."""
        by_source = Counter(
            source
            for sources in self.matched_source_by_path.values()
            for source in sources
        )
        bits = [f"{source} {count}" for source, count in sorted(by_source.items())]
        refreshed = self.matched - len(self.matched_source_by_path)
        if refreshed > 0:
            bits.append(f"{refreshed} refreshed from stored id")
        return ", ".join(bits)

    def summary(self, *, elapsed: str) -> str:
        """Format the end-of-session summary line."""
        matched = f"matched {self.matched}"
        breakdown = self._source_breakdown()
        if breakdown:
            matched += f" ({breakdown})"
        parts = [matched, f"{self.skipped} skipped"]
        if self.deferred:
            parts.append(f"{self.deferred} deferred for manual prompts")
        if self.errored:
            parts.append(f"{self.errored} errored")
        comics = "comic" if self.total == 1 else "comics"
        return (
            f"Online tag session finished in {elapsed}: "
            f"{self.total} {comics} — {', '.join(parts)}."
        )
