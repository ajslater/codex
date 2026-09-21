"""Group View."""

from typing import override

from django.contrib.auth.models import Group
from django.core.cache import cache

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

    # Serializer field names, which arrive here already un-camelized by
    # the JSON:API parser — never the camelCase spelling the client sent.
    _CHANGE_FIELDS = frozenset({"library_set", "user_set", "groupauth"})

    def _on_change(self, validated_data=None) -> None:
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
    def perform_update(self, serializer) -> None:
        """Perform update and run hooks."""
        validated_data = serializer.validated_data
        super().perform_update(serializer)
        self._on_change(validated_data)

    @override
    def perform_create(self, serializer) -> None:
        """Perform create and run hooks."""
        super().perform_create(serializer)
        # A brand new group always changes what the group lists show,
        # even when it arrives with nothing but a name.
        self._on_change()

    @override
    def perform_destroy(self, instance) -> None:
        """Perform destroy and run hooks."""
        super().perform_destroy(instance)
        self._on_change()
