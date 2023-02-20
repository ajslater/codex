"""Admin Flag View."""
from rest_framework.permissions import IsAdminUser
from rest_framework.viewsets import ModelViewSet

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.logger.logging import get_logger
from codex.models import AdminFlag
from codex.registration import patch_registration_setting
from codex.serializers.admin import AdminFlagSerializer

LOG = get_logger(__name__)


class AdminFlagViewSet(ModelViewSet):
    """Admin Flag Viewset."""

    permission_classes = [IsAdminUser]
    queryset = AdminFlag.objects.all()
    serializer_class = AdminFlagSerializer

    def _on_change(self):
        """Signal UI that its out of date."""
        pk = self.kwargs.get("pk")
        if AdminFlag.objects.filter(pk=pk, name=AdminFlag.ENABLE_REGISTRATION).exists():
            patch_registration_setting()
        # Heavy handed refresh everything, but simple.
        # Folder View could only change the group view and let the ui decide
        # Registration only needs to change the enable flag
        LIBRARIAN_QUEUE.put(LIBRARY_CHANGED_TASK)

    def perform_update(self, serializer):
        """Perform update and hook for change."""
        super().perform_update(serializer)
        self._on_change()
