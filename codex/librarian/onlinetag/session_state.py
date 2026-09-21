"""State and helpers for an in-flight online tagging scan."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from comicbox.online_session import PromptResponse

from codex.librarian.onlinetag.outcome_stats import OnlineTagOutcomeStats
from codex.librarian.onlinetag.session_cache import PROMPT_VERSION

#: What codex calls itself in comicbox's outgoing User-Agent. Every
#: comicbox session codex builds passes it — the scan's and the one a
#: prompt answer replays through — so a source's operators see one name
#: for all of codex's traffic.
CLIENT_NAME: Final = "codex"

if TYPE_CHECKING:
    from pathlib import Path

    from comicbox.online_session import OnlinePrompt, OnlineSession


@dataclass
class LiveLookup:
    """
    The (comic, source) codex is consulting right this instant.

    The authoritative answer to "what is the scan doing now", and the only
    input the snapshot's in-flight row and its "Looking up" cell are built
    from. Set from the comicbox event stream (``SourceStarted``) and from
    codex's own stored-id prepass, which runs outside the event-emitting
    session entirely.

    It replaces guessing the in-flight comic from ``path_to_pk`` position:
    ``tag_many`` re-sorts the batch by series fingerprint
    (comicbox ``online_session.py``, ``series_batching`` defaults on and codex
    never overrides it), so position says nothing about processing order.
    Unset means *nothing is live* — between comics, before the first event,
    after a cancel — and the snapshot then marks no row in flight rather than
    pointing confidently at an arbitrary one.

    Daemon-only and never serialized; the snapshot projects it at build time.
    A single scalar is complete and needs no lock because a scan is strictly
    sequential — one ``tag_many`` loop, one source at a time within a comic,
    and comicbox dispatches events inline on the calling thread.
    """

    path: Path | None = None
    source: str = ""

    def begin(self, path: Path, source: str) -> None:
        """Record that ``source`` is being consulted for ``path``."""
        self.path = path
        self.source = source

    def end(self, path: Path) -> None:
        """Clear the marker, but only if ``path`` is still the live comic."""
        # A FileFinished/FileError for some *earlier* comic (a late or
        # replayed event) must not wipe the comic being worked on now.
        if path == self.path:
            self.clear()

    def clear(self) -> None:
        """Nothing is live."""
        self.path = None
        self.source = ""


@dataclass
class SessionState:
    """Tracks a single online tagging scan (Pass 1)."""

    session: OnlineSession
    collected_tags: dict[int, dict[str, Any]] = field(default_factory=dict)
    path_to_pk: dict[Path, int] = field(default_factory=dict)
    pending_paths: list[Path] = field(default_factory=list)
    mode: str = "additive"
    # The comicbox match mode (auto/careful/eager) and enabled sources in
    # priority order — the inputs the time-remaining estimate needs. Distinct
    # from ``mode`` above, which is the tag-write mode.
    match_mode: str = "auto"
    sources: tuple[str, ...] = ()
    # How much API budget a comic may spend against a fan-out source.
    # Only Comic Vine fans out; it is what the time estimate turns on.
    effort: str = "balanced"

    # Whether this scan queries every source per comic and merges
    # (comicbox first_wins=False) — the time estimate needs it.
    merge_all_sources: bool = False
    formats: tuple[str, ...] = ("COMIC_INFO",)
    delete_original: bool = False
    # Rename each written archive to the comicbox filename scheme.
    rename: bool = False
    cancelled: bool = False
    # Why the scan stopped, when it was not the operator who stopped it —
    # today, a spent daily API quota. The status row is finished the moment a
    # pass ends, so a subtitle there would only flash; this rides the frozen
    # snapshot instead, which is what the admin is still looking at when they
    # come back to press Resume.
    pause_reason: str = ""
    total_comics: int = 0
    completed_comics: int = 0
    stats: OnlineTagOutcomeStats = field(default_factory=OnlineTagOutcomeStats)
    # What the scan is consulting right now — see LiveLookup.
    live: LiveLookup = field(default_factory=LiveLookup)
    # Comics the admin answered a prompt for *while this scan was running*.
    # The scan keeps re-persisting ``session.deferred_prompts()`` on every
    # PromptDeferred event (and once more at the end), which would otherwise
    # resurrect a just-answered prompt — see _persist_prompts.
    #
    # Keyed by comic, not by prompt fingerprint: comicbox fingerprints at
    # series level, so a fingerprint filter also swallowed the *later* issues
    # of an answered series, which nobody had answered for. They were dropped
    # silently and finished the scan untagged.
    answered_pks: set[int] = field(default_factory=set)
    # (prompt, action, payload, chosen_volume_id) tuples for "choose"/"manual"
    # answers received mid-scan. The cache removal happens inline (race-free,
    # on the librarian thread) but the network re-fetch + write is deferred to
    # after the scan releases the thread — see _apply_deferred_resolutions.
    deferred_applies: list[tuple[dict[str, Any], str, Any, int | None]] = field(
        default_factory=list
    )
    # The originating task's kwargs, persisted with the resume descriptor so a
    # killed/paused scan can be rebuilt into a fresh BulkOnlineTagTask over just
    # the comics it never reached — see session_snapshot.set_resume_state.
    resume_params: dict[str, Any] = field(default_factory=dict)


class CodexPromptHandler:
    """Fallback PromptHandler for non-deferred mode."""

    def request(self, prompt: OnlinePrompt) -> PromptResponse:
        """Skip by default — primary flow uses defer mode."""
        _ = prompt
        return PromptResponse(action="skip", payload=None)


def serialize_prompt(
    dp: Any,
    comics: list[dict[str, Any]],
    formats: tuple[str, ...],
    *,
    delete_original: bool,
    rename: bool,
) -> dict[str, Any]:
    """
    Serialize a deferred prompt with everything needed to apply it later.

    ``comics`` is every comic this one question answers for, ``dp``'s own
    comic first — comicbox fingerprints at series level, so one prompt
    stands for a whole series in the batch (see ``prompt_comics``). ``pk``
    and ``path`` repeat the representative so a prompt written by this
    codex still reads on a rollback to one that predates the list.
    """
    representative = comics[0]
    return {
        "fingerprint": dp.fingerprint,
        "prompt_version": PROMPT_VERSION,
        "pk": representative["pk"],
        "path": representative["path"],
        "comics": comics,
        "source": dp.source,
        "candidates": [serialize_candidate(c) for c in dp.candidates],
        "mode": getattr(dp.match, "value", str(dp.match)),
        "formats": list(formats),
        "delete_original": delete_original,
        "rename": rename,
    }


def serialize_candidate(c) -> dict[str, Any]:
    """
    Serialize a comicbox Candidate to a JSON-safe dict.

    Every field is read with ``getattr`` and a default so an older
    comicbox, or a shape that changes under us, degrades to a missing
    display field rather than an exception in the librarian.

    Adding display fields here must NOT bump ``PROMPT_VERSION``: that
    gates the fingerprint scheme, and raising it discards every prompt a
    user has pending. The frontend tolerates their absence instead.
    """
    summary = c.summary
    return {
        "source": c.source,
        "issue_id": c.issue_id,
        "summary": {
            "series": getattr(summary, "series", ""),
            "issue": getattr(summary, "issue", ""),
            "year": getattr(summary, "year", None),
            "publisher": getattr(summary, "publisher", ""),
            "cover_url": getattr(summary, "cover_url", ""),
            # The largest tier the source offers, when it offers one.
            # Comic Vine has several; Metron sets it equal to cover_url
            # because its one image is already full size. comicbox owns
            # the "genuinely larger" guarantee, so the frontend gates
            # the hover on this being truthy and never on it differing.
            "cover_url_full": getattr(summary, "cover_url_full", None),
            # Alternative series names comicbox scored this candidate on.
            # Empty for sources whose search results don't carry them.
            "alt_series": list(getattr(summary, "alt_series", ())),
            # The series' ordinal volume. Metron's issue rows carry one;
            # Comic Vine's search results have no equivalent.
            "volume": getattr(summary, "volume", None),
        },
        "score": c.score,
        # What the blended score is made of. Two candidates can read
        # identically — same series, issue and year — and differ only
        # here, which is exactly the case the reporter could not choose
        # between.
        "metadata_score": getattr(c, "metadata_score", None),
        # None when the cover was never compared: either this candidate
        # has no usable image, or it fell outside the top few the matcher
        # pays to hash. ``cover_hash_attempted`` tells those apart.
        "cover_score": getattr(c, "cover_score", None),
        "cover_hash_attempted": getattr(c, "cover_hash_attempted", False),
        "url": getattr(c, "url", ""),
        # The candidate's parent container id (CV volume, Metron series).
        # None for sources that don't expose it.
        "volume_id": getattr(c, "volume_id", None),
    }
