"""State and helpers for an in-flight online tagging scan."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from comicbox.online_session import PromptResponse

from codex.librarian.onlinetag.outcome_stats import OnlineTagOutcomeStats

if TYPE_CHECKING:
    from pathlib import Path

    from comicbox.online_session import OnlinePrompt, OnlineSession


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
    # Whether this scan queries every source per comic and merges
    # (comicbox first_wins=False) — the time estimate needs it.
    merge_all_sources: bool = False
    formats: tuple[str, ...] = ("COMIC_INFO",)
    delete_original: bool = False
    # Rename each written archive to the comicbox filename scheme.
    rename: bool = False
    cancelled: bool = False
    total_comics: int = 0
    completed_comics: int = 0
    stats: OnlineTagOutcomeStats = field(default_factory=OnlineTagOutcomeStats)
    # Prompt fingerprints the admin answered *while this scan was running*.
    # The scan keeps re-persisting ``session.deferred_prompts()`` on every
    # PromptDeferred event (and once more at the end), which would otherwise
    # resurrect a just-answered prompt — see _persist_prompts.
    answered_fingerprints: set[str] = field(default_factory=set)
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


def serialize_candidate(c) -> dict[str, Any]:
    """Serialize a comicbox Candidate to a JSON-safe dict."""
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
        },
        "score": c.score,
        "url": getattr(c, "url", ""),
    }
