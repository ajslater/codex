"""Online tagging tasks."""

from dataclasses import dataclass
from typing import Any

from codex.librarian.tasks import LibrarianTask


class OnlineTagTask(LibrarianTask):
    """Base task for online tagging thread."""


@dataclass
class BulkOnlineTagTask(OnlineTagTask):
    """Start an online tagging session for a set of comics."""

    comic_pks: frozenset[int]
    session_id: str
    sources: tuple[str, ...] = ("metron", "comicvine")
    mode: str = "normal"
    prompts_mode: str = "ask"
    effort: str = "balanced"
    auto_threshold: float = 0.85
    delete_original: bool = False
    dry_run: bool = False


@dataclass
class OnlineTagAbortTask(OnlineTagTask):
    """Abort an online tagging session."""

    session_id: str = ""


@dataclass
class OnlineTagPromptResponseTask(OnlineTagTask):
    """Admin response to a deferred online tagging prompt."""

    session_id: str = ""
    prompt_fingerprint: str = ""
    action: str = "skip"
    payload: Any = None
    chosen_volume_id: int | None = None
