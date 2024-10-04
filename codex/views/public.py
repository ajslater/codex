"""Public non-authenticated views."""

from rest_framework.generics import GenericAPIView
from rest_framework.mixins import RetrieveModelMixin

from codex.choices import ADMIN_FLAG_CHOICES
from codex.logger.logging import get_logger
from codex.models import AdminFlag
from codex.serializers.auth import AuthAdminFlagsSerializer

LOG = get_logger(__name__)
_ADMIN_FLAG_KEYS = frozenset(
    {
        AdminFlag.FlagChoices.NON_USERS.value,
        AdminFlag.FlagChoices.REGISTRATION.value,
    }
)


class AdminFlagsView(GenericAPIView, RetrieveModelMixin):
    """Get admin flags relevant to auth."""

    serializer_class = AuthAdminFlagsSerializer
    queryset = AdminFlag.objects.filter(key__in=_ADMIN_FLAG_KEYS).only("key", "on")

    def get_object(self):
        """Get admin flags."""
        flags = {}
        for obj in self.get_queryset():  # type: ignore
            name = ADMIN_FLAG_CHOICES[obj.key].lower().replace(" ", "_")
            flags[name] = obj.on
        return flags

    def get(self, request, *args, **kwargs):
        """Get admin flags relevant to auth."""
        return self.retrieve(request, *args, **kwargs)
