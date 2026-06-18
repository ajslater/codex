"""Online tagging librarian thread."""

from typing import override

from codex.librarian.onlinetag.session_cache import set_active_scan_id
from codex.librarian.onlinetag.session_manager import OnlineTagSessionManager
from codex.librarian.onlinetag.session_snapshot import deactivate_snapshot
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagAbortTask,
    OnlineTagByIdTask,
    OnlineTagDismissTask,
    OnlineTagPromptResponseTask,
    OnlineTagSkipAllPromptsTask,
)
from codex.librarian.threads import QueuedThread


class OnlineTagThread(QueuedThread):
    """Thread for managing online tagging sessions."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize session manager."""
        super().__init__(*args, **kwargs)
        self._session_manager: OnlineTagSessionManager | None = None

    @property
    def session_manager(self) -> OnlineTagSessionManager:
        """Lazy-init the session manager."""
        if self._session_manager is None:
            self._session_manager = OnlineTagSessionManager(
                self.log, self.librarian_queue, self.queue
            )
        return self._session_manager

    def has_active_session(self, session_id: str) -> bool:
        """Whether ``session_id`` is currently running in-memory."""
        if self._session_manager is None:
            return False
        return self._session_manager.has_session(session_id)

    @override
    def run_start(self) -> None:
        """
        Clear only the active-scan marker before entering the loop.

        An in-flight Pass-1 scan cannot survive a process restart, so its
        cached marker is orphan. Pending prompts, by contrast, are designed
        to linger across restarts and are deliberately left untouched.
        """
        super().run_start()
        try:
            set_active_scan_id("")
            # A snapshot left "active" by a scan that the restart killed would
            # read as still-running; flip it to inactive (keeping the last
            # tally) rather than deleting it.
            deactivate_snapshot()
        except Exception:
            self.log.exception("Clearing stale online tag scan marker on startup")

    @override
    def process_item(self, item) -> None:
        """Dispatch online tag tasks."""
        match item:
            case BulkOnlineTagTask():
                self.session_manager.run_session(item)
            case OnlineTagByIdTask():
                self.session_manager.tag_by_id(item)
            case OnlineTagAbortTask():
                self.session_manager.cancel_session(item.session_id)
            case OnlineTagPromptResponseTask():
                self.session_manager.resolve_prompt(
                    item.prompt_fingerprint,
                    item.action,
                    item.payload,
                    item.chosen_volume_id,
                )
            case OnlineTagSkipAllPromptsTask():
                self.session_manager.skip_all_prompts()
            case OnlineTagDismissTask():
                self.session_manager.dismiss_session()
            case _:
                self.log.warning(f"Bad task sent to online tag thread: {item}")
