"""Group View."""
from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework.permissions import IsAdminUser
from rest_framework.viewsets import ModelViewSet

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.serializers.admin import GroupSerializer
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class AdminGroupViewSet(ModelViewSet):
    """Admin Group Viewset."""

    permission_classes = [IsAdminUser]
    queryset = Group.objects.prefetch_related("user_set", "library_set").defer(
        "permissions"
    )
    serializer_class = GroupSerializer

    CHANGE_FIELDS = frozenset(("librarySet", "userSet"))

    def _on_change(self, validated_keys):
        """On change hook."""
        if validated_keys.intersection(self.CHANGE_FIELDS):
            cache.clear()
            LIBRARIAN_QUEUE.put(LIBRARY_CHANGED_TASK)

    def get_serializer(self, *args, **kwargs):
        """Allow creation with the model serializer without users & libraries."""
        kwargs["partial"] = True
        return super().get_serializer(*args, **kwargs)

    def perform_update(self, serializer):
        """Perform update and run hooks."""
        validated_keys = frozenset(serializer.validated_data.keys())
        super().perform_update(serializer)
        self._on_change(validated_keys)

    def perform_create(self, serializer):
        """Perform create and run hooks."""
        validated_keys = frozenset(serializer.validated_data.keys())
        super().perform_create(serializer)
        self._on_change(validated_keys)

    def perform_destroy(self, instance):
        """Perform destroy and run hooks."""
        super().perform_destroy(instance)
        self._on_change(self.CHANGE_FIELDS)
