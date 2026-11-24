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

Alongside those file-level buckets, ``source_status_by_path`` folds the
per-source events (every one carries both ``path`` and ``source``) into a
"what did each source do with this comic" map, which the snapshot renders as
one status table column per source. It records only *outcomes* — matched,
no-match, needs-review — never work in progress: what a source is doing right
now lives on :class:`~codex.librarian.onlinetag.session_state.LiveLookup` and
is projected into the snapshot at build time. Keeping liveness out of here is
what makes a stale "still searching" cell impossible.

Not every source that runs reports one of those outcomes — a search with zero
candidates, a search that raises, and a comic with nothing to search on all end
a source's turn silently. ``FileFinished`` therefore closes the comic: every
source that announced itself (``SourceStarted``) without reporting settles as
no-match, so an empty cell means only what it looks like — that source never
ran on this comic.

One scan runs on a single daemon thread and emits its events inline, so the
tallies need no locking.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from comicbox.events import (
    SKIP_QUOTA_RESERVED,
    AutoWritten,
    FileError,
    FileFinished,
    NoMatch,
    PromptDeferred,
    Skipped,
    SourceStarted,
)

from codex.librarian.onlinetag.issue_id import parse_issue_id
from codex.librarian.onlinetag.statuses import (
    MATCHED,
    NEEDS_REVIEW,
    NO_MATCH,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from pathlib import Path

    from comicbox.events import Event


@dataclass
class OnlineTagOutcomeStats:
    """Accumulate per-comic online-tagging outcomes for an end-of-session summary."""

    matched_source_by_path: dict[Path, list[str]] = field(default_factory=dict)
    # The issue id each source auto-wrote a comic with. A prompt another
    # source defers on the comic carries these, so answering it can fetch
    # them again and let comicbox merge in the run's order: the scan writes
    # only when it ends, so the database learns them too late.
    matched_ids_by_path: dict[Path, dict[str, int]] = field(default_factory=dict)
    source_status_by_path: dict[Path, dict[str, str]] = field(default_factory=dict)
    # Sources that actually ran on a comic, so the ones that finished
    # without saying anything can still be told from the ones that never
    # started. Comicbox emits SourceStarted after its first-wins skip, so
    # a source that sat out is absent here.
    started_sources_by_path: dict[Path, list[str]] = field(default_factory=dict)
    written_paths: set[Path] = field(default_factory=set)
    no_change_paths: set[Path] = field(default_factory=set)
    deferred_paths: set[Path] = field(default_factory=set)
    errored_paths: set[Path] = field(default_factory=set)
    # Comics a source declined to look up because its daily API quota was
    # spent or down to its reserve. Deliberately NOT an outcome: that source
    # never looked, so unless another source settled the comic it stays out
    # of the terminal buckets and in the resume set for the next run,
    # instead of being recorded as a comic no source could find.
    quota_reserved_paths: set[Path] = field(default_factory=set)

    def record(self, event: Event) -> None:
        """Fold one comicbox event into the running tallies."""
        self._record_outcome(event)
        self._record_source_status(event)

    def _record_outcome(self, event: Event) -> None:
        """Fold one event into the file-level outcome buckets."""
        match event:
            case AutoWritten(path=path, source=source, candidate_summary=summary) if (
                path and source
            ):
                self._add_matched_source(path, source)
                self._add_matched_id(path, source, summary)
            case Skipped(path=path, reason=reason) if (
                path and reason == SKIP_QUOTA_RESERVED
            ):
                self.quota_reserved_paths.add(path)
            case FileFinished(path=path, outcome=outcome) if path:
                self._record_finished(path, outcome)
            case PromptDeferred(path=path) if path:
                self.deferred_paths.add(path)
            case FileError(path=path) if path:
                self.errored_paths.add(path)
            case _:
                pass

    def _record_finished(self, path: Path, outcome: str) -> None:
        """Put a finished comic in its terminal bucket, if it has one."""
        if outcome == "written":
            self.written_paths.add(path)
        elif path not in self.quota_reserved_paths or path in self.deferred_paths:
            # A comic the quota reserve skipped finishes "no_change" like any
            # unmatched one, but it is not a miss — it was never searched
            # for. Leaving it out of the bucket keeps it queued and
            # resumable. One another source deferred for review is settled
            # all the same: it waits on that prompt, not on the next run.
            self.no_change_paths.add(path)

    def _record_source_status(self, event: Event) -> None:
        """
        Fold one event into the per-comic, per-source status map.

        The two lifecycle events bracket a source's turn — one says a source
        is about to run, the other says the comic is done and whatever never
        reported has to settle. Everything else that belongs in the map is a
        verdict from one source about one comic.
        """
        match event:
            case SourceStarted(path=path, source=source) if path and source:
                self._add_started_source(path, source)
            case FileFinished(path=path) if path:
                self._close_source_statuses(path)
            case _:
                self._record_source_verdict(event)

    def _record_source_verdict(self, event: Event) -> None:
        """Record what one source concluded about one comic, if anything."""
        match event:
            case AutoWritten(path=path, source=source) if path and source:
                status = MATCHED
            # Before the general Skipped case below, which would otherwise
            # claim it: a source that never searched reports nothing about
            # this comic, so its cell stays empty rather than saying "no
            # match" about a lookup that never happened.
            case Skipped(reason=reason) if reason == SKIP_QUOTA_RESERVED:
                return
            # A source that found nothing above the confidence floor and one
            # whose matcher declined both mean "this source did not tag it" —
            # the same distinction the file-level pipeline already collapses.
            case (
                NoMatch(path=path, source=source) | Skipped(path=path, source=source)
            ) if path and source:
                status = NO_MATCH
            case PromptDeferred(path=path, source=source) if path and source:
                status = NEEDS_REVIEW
            case _:
                return
        self._set_source_status(path, source, status)

    def _add_matched_source(self, path: Path, source: str) -> None:
        """
        Attribute a match to the source that won it, deduped in win order.

        Under merge_all_sources a comic can be auto-written by more than one
        source, so accumulate rather than letting the last event clobber the
        first.
        """
        sources = self.matched_source_by_path.setdefault(path, [])
        if source not in sources:
            sources.append(source)

    def _add_matched_id(self, path: Path, source: str, summary: str) -> None:
        """
        Note the issue id a source auto-wrote a comic with.

        comicbox's ``AutoWritten`` names the id it fetched as the event's
        ``candidate_summary`` on every route to a win; anything that does
        not parse as an id is left out rather than guessed at.
        """
        if (issue_id := parse_issue_id(summary)) is not None:
            self.matched_ids_by_path.setdefault(path, {})[source] = issue_id

    def _add_started_source(self, path: Path, source: str) -> None:
        """Note that a source ran on a comic, deduped in start order."""
        started = self.started_sources_by_path.setdefault(path, [])
        if source not in started:
            started.append(source)

    def _set_source_status(self, path: Path, source: str, status: str) -> None:
        """Record what one source is doing (or did) with one comic."""
        self.source_status_by_path.setdefault(path, {})[source] = status

    def _close_source_statuses(self, path: Path) -> None:
        """
        Settle every source that ran on this comic but never reported.

        Comicbox has terminal events only for the resolutions its matcher
        reaches. A search that comes back with zero candidates, one that
        raises, and a comic with nothing to search on all end that
        source's turn in silence — and the status table renders a cell-less
        source as an em-dash, which reads as "never attempted", the one
        thing that did not happen. A source that ran and did not tag the
        comic did not match it, whichever of those it was.
        """
        cells = self.source_status_by_path.setdefault(path, {})
        for source in self.started_sources_by_path.get(path, ()):
            cells.setdefault(source, NO_MATCH)

    def record_prefetch_match(self, path: Path, sources: Collection[str]) -> None:
        """
        Record a comic matched from its stored ids before the search pass.

        The prepass fetches by id outside the event-emitting session, so it
        seeds by hand what an ``AutoWritten`` + ``FileFinished`` pair would.
        Every source whose id landed is credited, not just the primary: a
        merged fetch writes all of their tags, and crediting one leaves the
        others reading as never consulted.
        """
        self.written_paths.add(path)
        for source in sources:
            self._add_matched_source(path, source)
            self._set_source_status(path, source, MATCHED)

    def forget(self, path: Path) -> None:
        """Drop everything recorded for ``path``, as if no lookup had run."""
        for paths in (
            self.written_paths,
            self.no_change_paths,
            self.deferred_paths,
            self.errored_paths,
            self.quota_reserved_paths,
        ):
            paths.discard(path)
        for by_path in (
            self.matched_source_by_path,
            self.matched_ids_by_path,
            self.source_status_by_path,
            self.started_sources_by_path,
        ):
            by_path.pop(path, None)

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
    def left_for_next_run(self) -> int:
        """
        Comics a quota kept a source from, that no other source settled.

        Under merge-all a comic can be quota-skipped by one source and written
        or deferred by another; it is done, so counting it here too would
        report one comic twice.
        """
        settled = self.written_paths | self.no_change_paths | self.errored_paths
        return len(self.quota_reserved_paths - settled)

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
        if reserved := self.left_for_next_run:
            parts.append(f"{reserved} left for the next run (daily API quota)")
        if self.errored:
            parts.append(f"{self.errored} errored")
        comics = "comic" if self.total == 1 else "comics"
        return (
            f"Online tag session finished in {elapsed}: "
            f"{self.total} {comics} — {', '.join(parts)}."
        )


def api_cost_lines(snapshot: Mapping[str, Any]) -> list[str]:
    """
    Render what a session spent at each API, one line per source.

    Counts real HTTP sends, which comicbox 5.1 records at the one place a
    request leaves the process — so these numbers line up with the server's
    own logs, which is what makes them worth pasting into a bug report. The
    remaining budget is what the server last reported, so a run that ends
    near the daily floor says so in the same breath as the pause that the
    floor caused.
    """
    lines = []
    for source in sorted(snapshot):
        api = snapshot[source]
        requests = dict(getattr(api, "requests", {}) or {})
        total = sum(requests.values())
        rejections = getattr(api, "rejections", 0)
        if not total and not rejections:
            continue
        breakdown = ", ".join(f"{n} {name}" for name, n in sorted(requests.items()))
        line = f"Online tag {source} API: {total} requests ({breakdown})"
        detail = []
        if rejections:
            detail.append(f"{rejections} rate-limited")
        blocked = getattr(api, "blocked_seconds", 0.0)
        if blocked >= 1.0:
            detail.append(f"{blocked:.0f}s paced")
        budget = _budget_phrase(api)
        if budget:
            detail.append(f"{budget} left")
        if detail:
            line += f" — {', '.join(detail)}"
        lines.append(line + ".")
    return lines


def _budget_phrase(api: Any) -> str:
    """Render whichever rate-limit windows the server reported."""
    parts = []
    burst_remaining = getattr(api, "burst_remaining", None)
    if burst_remaining is not None:
        burst_limit = getattr(api, "burst_limit", None)
        limit = f"/{burst_limit}" if burst_limit is not None else ""
        parts.append(f"{burst_remaining}{limit} this minute")
    sustained_remaining = getattr(api, "sustained_remaining", None)
    if sustained_remaining is not None:
        sustained_limit = getattr(api, "sustained_limit", None)
        limit = f"/{sustained_limit}" if sustained_limit is not None else ""
        parts.append(f"{sustained_remaining}{limit} today")
    return ", ".join(parts)
