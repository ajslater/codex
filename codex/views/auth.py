"""Views authorization."""
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from codex.models import AdminFlag
from codex.serializers.auth import AuthAdminFlagsSerializer, TimezoneSerializer
from codex.serializers.mixins import OKSerializer
from codex.settings.logging import get_logger


LOG = get_logger(__name__)
NULL_USER = {"pk": None, "username": None, "is_staff": False}


class IsAuthenticatedOrEnabledNonUsers(IsAuthenticated):
    """Custom DRF Authentication class."""

    code = 403

    def has_permission(self, request, view):
        """Return True if ENABLE_NON_USERS is true or user authenticated."""
        enu_flag = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_NON_USERS)
        if enu_flag.on:
            return True
        return super().has_permission(request, view)


class TimezoneView(GenericAPIView):
    """User info."""

    input_serializer_class = TimezoneSerializer
    serializer_class = OKSerializer

    @extend_schema(request=input_serializer_class)
    def post(self, request, *args, **kwargs):
        """Get the user info for the current user."""
        serializer = self.input_serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        request.session["django_timezone"] = serializer.validated_data["timezone"]
        request.session.save()
        serializer = self.get_serializer()
        return Response(serializer.data)


class AdminFlagsView(GenericAPIView, RetrieveModelMixin):
    """Get admin flags relevant to auth."""

    _ADMIN_FLAG_NAMES = frozenset(
        (AdminFlag.ENABLE_NON_USERS, AdminFlag.ENABLE_REGISTRATION)
    )

    serializer_class = AuthAdminFlagsSerializer
    queryset = AdminFlag.objects.filter(name__in=_ADMIN_FLAG_NAMES).only("name", "on")

    def get_object(self):
        """Get admin flags."""
        flags = {}
        for obj in self.get_queryset():  # type: ignore
            # XXX this key munging is a hack AdminFlags should be a TextChoices
            key = obj.name.lower().replace(" ", "_")
            flags[key] = obj.on
        return flags

    def get(self, request, *args, **kwargs):
        """Get admin flags relevant to auth."""
        return self.retrieve(request, *args, **kwargs)
