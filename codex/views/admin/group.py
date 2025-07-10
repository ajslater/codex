"""Group View."""

from django.contrib.auth.models import Group
from django.core.cache import cache
from typing_extensions import override

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import GROUPS_CHANGED_TASK
from codex.serializers.admin.groups import GroupSerializer
from codex.views.admin.auth import AdminModelViewSet


class AdminGroupViewSet(AdminModelViewSet):
    """Admin Group Viewset."""

    queryset = Group.objects.prefetch_related("user_set", "library_set").select_related(
        "groupauth"
    )
    serializer_class = GroupSerializer

    _CHANGE_FIELDS = frozenset({"librarySet", "userSet", "groupauth"})

    def _on_change(self, validated_data=None):
        """On change hook."""
        if not validated_data or frozenset(validated_data.keys()).intersection(
            self._CHANGE_FIELDS
        ):
            cache.clear()
            LIBRARIAN_QUEUE.put(GROUPS_CHANGED_TASK)

    @override
    def get_serializer(self, *args, **kwargs):
        """Allow creation with the model serializer without users & libraries."""
        kwargs["partial"] = True
        return super().get_serializer(*args, **kwargs)

    @override
    def perform_update(self, serializer):
        """Perform update and run hooks."""
        validated_data = serializer.validated_data
        super().perform_update(serializer)
        self._on_change(validated_data)

    @override
    def perform_create(self, serializer):
        """Perform create and run hooks."""
        validated_data = serializer.validated_data
        super().perform_create(serializer)
        self._on_change(validated_data)

    @override
    def perform_destroy(self, instance):
        """Perform destroy and run hooks."""
        super().perform_destroy(instance)
        self._on_change()
