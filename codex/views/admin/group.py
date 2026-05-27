"""Group View."""

from typing import override

from django.contrib.auth.models import Group
from django.core.cache import cache

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import groups_changed_task
from codex.serializers.admin.groups import GroupSerializer
from codex.views.admin.auth import AdminModelViewSet


class AdminGroupViewSet(AdminModelViewSet):
    """Admin Group Viewset."""

    queryset = Group.objects.prefetch_related("user_set", "library_set").select_related(
        "groupauth"
    )
    serializer_class = GroupSerializer

    _CHANGE_FIELDS = frozenset({"librarySet", "userSet", "groupauth"})

    def _on_change(self, validated_data=None, instance=None) -> None:
        """On change hook."""
        if not validated_data or frozenset(validated_data.keys()).intersection(
            self._CHANGE_FIELDS
        ):
            cache.clear()
            ids = [instance.pk] if instance is not None else None
            LIBRARIAN_QUEUE.put(groups_changed_task(ids=ids))

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
        self._on_change(validated_data, serializer.instance)

    @override
    def perform_create(self, serializer) -> None:
        """Perform create and run hooks."""
        validated_data = serializer.validated_data
        super().perform_create(serializer)
        self._on_change(validated_data, serializer.instance)

    @override
    def perform_destroy(self, instance) -> None:
        """Perform destroy and run hooks."""
        pk = instance.pk
        super().perform_destroy(instance)
        # Synthesize an instance shim so the notify scope still carries
        # the now-deleted group's pk.
        self._on_change(instance=type("Deleted", (), {"pk": pk})())
