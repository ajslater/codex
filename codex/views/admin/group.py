"""Group View."""

from typing import ClassVar

from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework.permissions import IsAdminUser
from rest_framework.viewsets import ModelViewSet

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.logger.logging import get_logger
from codex.models.admin import GroupAuth
from codex.serializers.admin import GroupSerializer

LOG = get_logger(__name__)


class AdminGroupViewSet(ModelViewSet):
    """Admin Group Viewset."""

    permission_classes: ClassVar[list] = [IsAdminUser]  # type: ignore
    queryset = Group.objects.prefetch_related("user_set", "library_set").select_related(
        "groupauth"
    )
    serializer_class = GroupSerializer

    _CHANGE_FIELDS = frozenset({"librarySet", "userSet", "exclude"})

    def _on_change(self, validated_data=None):
        """On change hook."""
        if validated_data:
            pk = self.kwargs.get("pk")
            if pk:
                group = Group.objects.get(pk=pk)
            else:
                name = validated_data.get("name")
                group = Group.objects.get(name=name)
            exclude = bool(validated_data.get("exclude"))
            defaults = {"group": group}
            ga, _ = GroupAuth.objects.get_or_create(defaults=defaults, group=group)
            ga.exclude = exclude
            ga.save()

        if not validated_data or frozenset(validated_data.keys()).intersection(
            self._CHANGE_FIELDS
        ):
            cache.clear()
            LIBRARIAN_QUEUE.put(LIBRARY_CHANGED_TASK)

    def get_serializer(self, *args, **kwargs):
        """Allow creation with the model serializer without users & libraries."""
        kwargs["partial"] = True
        return super().get_serializer(*args, **kwargs)

    def perform_update(self, serializer):
        """Perform update and run hooks."""
        validated_data = serializer.validated_data
        super().perform_update(serializer)
        self._on_change(validated_data)

    def perform_create(self, serializer):
        """Perform create and run hooks."""
        validated_data = serializer.validated_data
        super().perform_create(serializer)
        self._on_change(validated_data)

    def perform_destroy(self, instance):
        """Perform destroy and run hooks."""
        super().perform_destroy(instance)
        self._on_change()
