"""State and helpers for an in-flight online tagging session."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from comicbox.online_session import PromptResponse

if TYPE_CHECKING:
    from pathlib import Path

    from comicbox.online_session import DeferredPrompt, OnlinePrompt, OnlineSession


@dataclass
class SessionState:
    """Tracks a single online tagging session."""

    session: OnlineSession
    collected_tags: dict[int, dict[str, Any]] = field(default_factory=dict)
    deferred_prompts: list[DeferredPrompt] = field(default_factory=list)
    resolved_count: int = 0
    total_prompts: int = 0
    event: threading.Event = field(default_factory=threading.Event)
    path_to_pk: dict[Path, int] = field(default_factory=dict)
    pending_paths: list[Path] = field(default_factory=list)
    mode: str = "additive"
    formats: tuple[str, ...] = ("COMIC_INFO",)
    delete_original: bool = False
    cancelled: bool = False
    total_comics: int = 0
    completed_comics: int = 0


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
