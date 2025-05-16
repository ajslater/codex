"""Public non-authenticated views."""

from rest_framework.generics import GenericAPIView
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.serializers import BaseSerializer
from typing_extensions import override

from codex.choices.admin import ADMIN_FLAG_CHOICES, AdminFlagChoices
from codex.models import AdminFlag
from codex.serializers.auth import AuthAdminFlagsSerializer

_ADMIN_FLAG_KEYS = frozenset(
    {
        AdminFlagChoices.NON_USERS.value,
        AdminFlagChoices.REGISTRATION.value,
        AdminFlagChoices.BANNER_TEXT.value,
    }
)


class AdminFlagsView(GenericAPIView, RetrieveModelMixin):
    """Get admin flags relevant to auth."""

    serializer_class: type[BaseSerializer] | None = AuthAdminFlagsSerializer
    queryset = AdminFlag.objects.filter(key__in=_ADMIN_FLAG_KEYS).only(
        "key", "on", "value"
    )

    @override
    def get_object(self):
        """Get admin flags."""
        flags = {}
        for obj in self.get_queryset():
            name = ADMIN_FLAG_CHOICES[obj.key].lower().replace(" ", "_")
            val = obj.value if obj.key == AdminFlagChoices.BANNER_TEXT.value else obj.on
            flags[name] = val
        return flags

    def get(self, *args, **kwargs):
        """Get admin flags relevant to auth."""
        return self.retrieve(*args, **kwargs)
