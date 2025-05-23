"""Admin Flag View."""

from typing_extensions import override

from codex.choices.admin import AdminFlagChoices
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import ADMIN_FLAGS_CHANGED_TASK
from codex.librarian.tasks import WakeCronTask
from codex.models import AdminFlag
from codex.serializers.admin.flags import AdminFlagSerializer
from codex.startup.registration import patch_registration_setting
from codex.views.admin.auth import AdminModelViewSet

_REFRESH_LIBRARY_FLAGS = frozenset(
    flag.value
    for flag in (
        AdminFlagChoices.FOLDER_VIEW,
        AdminFlagChoices.NON_USERS,
        AdminFlagChoices.BANNER_TEXT,
    )
)


class AdminFlagViewSet(AdminModelViewSet):
    """Admin Flag Viewset."""

    queryset = AdminFlag.objects.all()
    serializer_class = AdminFlagSerializer
    lookup_field = "key"

    def _on_change(self):
        """Signal UI that its out of date."""
        key = self.kwargs.get("key")
        if key == AdminFlagChoices.REGISTRATION.value:
            patch_registration_setting()
        elif key == AdminFlagChoices.SEND_TELEMETRY.value:
            LIBRARIAN_QUEUE.put(WakeCronTask())
        # Heavy handed refresh everything, but simple.
        # Folder View could only change the group view and let the ui decide
        # Registration only needs to change the enable flag
        if key in _REFRESH_LIBRARY_FLAGS:
            LIBRARIAN_QUEUE.put(ADMIN_FLAGS_CHANGED_TASK)

    @override
    def perform_update(self, serializer):
        """Perform update and hook for change."""
        super().perform_update(serializer)
        self._on_change()
