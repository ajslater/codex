"""
Admin Failed Imports Seen marker view.

Persists the moment an admin last cleared the failed-import warning so the
hamburger badge / sidebar item stay cleared across reloads and sessions. The
warning re-appears only for failed imports created after this marker. Stored in
the keyed ``Timestamp`` singleton (key ``FI``); an empty value means "never
cleared", so every failed import counts as unseen.
"""

from django.utils import timezone
from rest_framework.response import Response

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import FAILED_IMPORTS_CHANGED_TASK
from codex.models import Timestamp
from codex.views.admin.auth import AdminAPIView

_SEEN_KEY = Timestamp.Choices.FAILED_IMPORTS_SEEN.value


class AdminFailedImportsSeenView(AdminAPIView):
    """Read and update the failed-imports "seen" marker (an ISO timestamp)."""

    @staticmethod
    def _seen_at() -> str:
        row = Timestamp.objects.filter(key=_SEEN_KEY).only("value").first()
        return row.value if row else ""

    def get(self, _request, *_args, **_kwargs) -> Response:
        """Return the last-cleared timestamp (ISO 8601, or empty if never)."""
        return Response({"seen_at": self._seen_at()})

    def put(self, _request, *_args, **_kwargs) -> Response:
        """Mark all current failed imports as seen, then notify other admins."""
        now_iso = timezone.now().isoformat()
        Timestamp.objects.update_or_create(key=_SEEN_KEY, defaults={"value": now_iso})
        # Tell other admin sessions to re-evaluate their badge / sidebar item.
        LIBRARIAN_QUEUE.put(FAILED_IMPORTS_CHANGED_TASK)
        return Response({"seen_at": now_iso})
