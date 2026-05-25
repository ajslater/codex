"""Online tagging librarian thread."""

from typing import override

from codex.librarian.onlinetag.session_manager import OnlineTagSessionManager
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagAbortTask,
    OnlineTagPromptResponseTask,
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

    @override
    def process_item(self, item) -> None:
        """Dispatch online tag tasks."""
        match item:
            case BulkOnlineTagTask():
                self.session_manager.run_session(item)
            case OnlineTagAbortTask():
                self.session_manager.cancel_session(item.session_id)
            case OnlineTagPromptResponseTask():
                self.session_manager.resolve_prompt(
                    item.session_id,
                    item.prompt_fingerprint,
                    item.action,
                    item.payload,
                    item.chosen_volume_id,
                )
            case _:
                self.log.warning(f"Bad task sent to online tag thread: {item}")
