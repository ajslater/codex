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
    mode: str = "auto"
    prompts_mode: str = "ask"
    effort: str = "balanced"
    auto_threshold: float = 0.85
    delete_original: bool = False
    dry_run: bool = False
    # Query every source per comic and merge (comicbox first_wins=False)
    # instead of stopping at the first match.
    merge_all_sources: bool = False


@dataclass
class OnlineTagAbortTask(OnlineTagTask):
    """Abort an online tagging session."""

    session_id: str = ""


@dataclass
class OnlineTagByIdTask(OnlineTagTask):
    """Tag one comic by a known online issue id (skips search)."""

    comic_pk: int
    source: str
    issue_id: int
    formats: tuple[str, ...] = ("COMIC_INFO",)
    delete_original: bool = False
    # Additional (source, issue_id) pairs to fetch by explicit id and merge
    # onto the primary fetch — the Tag-by-id "merge all sources" path. Empty
    # means a single-source fetch.
    extra_ids: tuple[tuple[str, int], ...] = ()


@dataclass
class OnlineTagPromptResponseTask(OnlineTagTask):
    """Admin response to a deferred online tagging prompt (keyed by fingerprint)."""

    prompt_fingerprint: str = ""
    action: str = "skip"
    payload: Any = None
    chosen_volume_id: int | None = None


@dataclass
class OnlineTagSkipAllPromptsTask(OnlineTagTask):
    """Skip every pending deferred prompt in one shot."""
