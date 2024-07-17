"""Admin Flag View."""

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.tasks import WakeCronTask
from codex.logger.logging import get_logger
from codex.models import AdminFlag
from codex.registration import patch_registration_setting
from codex.serializers.admin.flags import AdminFlagSerializer
from codex.views.admin.auth import AdminModelViewSet

LOG = get_logger(__name__)

_REFRESH_LIBRARY_FLAGS = frozenset(
    flag.value
    for flag in (AdminFlag.FlagChoices.FOLDER_VIEW, AdminFlag.FlagChoices.NON_USERS)
)


class AdminFlagViewSet(AdminModelViewSet):
    """Admin Flag Viewset."""

    queryset = AdminFlag.objects.all()
    serializer_class = AdminFlagSerializer
    lookup_field = "key"

    def _on_change(self):
        """Signal UI that its out of date."""
        key = self.kwargs.get("key")
        if key == AdminFlag.FlagChoices.REGISTRATION.value:
            patch_registration_setting()
        elif key == AdminFlag.FlagChoices.SEND_TELEMETRY.value:
            LIBRARIAN_QUEUE.put(WakeCronTask())
        # Heavy handed refresh everything, but simple.
        # Folder View could only change the group view and let the ui decide
        # Registration only needs to change the enable flag
        if key in _REFRESH_LIBRARY_FLAGS:
            LIBRARIAN_QUEUE.put(LIBRARY_CHANGED_TASK)

    def perform_update(self, serializer):
        """Perform update and hook for change."""
        super().perform_update(serializer)
        self._on_change()
