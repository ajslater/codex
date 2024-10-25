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
        AdminFlag.FlagChoices.BANNER_TEXT.value,
    }
)


class AdminFlagsView(GenericAPIView, RetrieveModelMixin):
    """Get admin flags relevant to auth."""

    serializer_class = AuthAdminFlagsSerializer
    queryset = AdminFlag.objects.filter(key__in=_ADMIN_FLAG_KEYS).only(
        "key", "on", "value"
    )

    def get_object(self):
        """Get admin flags."""
        flags = {}
        for obj in self.get_queryset():
            name = ADMIN_FLAG_CHOICES[obj.key].lower().replace(" ", "_")
            if obj.key == AdminFlag.FlagChoices.BANNER_TEXT.value:
                val = obj.value
            else:
                val = obj.on
            flags[name] = val
        return flags

    def get(self, *args, **kwargs):
        """Get admin flags relevant to auth."""
        return self.retrieve(*args, **kwargs)
