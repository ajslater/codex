"""Views authorization."""
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import AdminFlag, UserActive
from codex.serializers.auth import AuthAdminFlagsSerializer, TimezoneSerializer
from codex.serializers.choices import CHOICES
from codex.serializers.mixins import OKSerializer

LOG = get_logger(__name__)
NULL_USER = {"pk": None, "username": None, "is_staff": False}


class IsAuthenticatedOrEnabledNonUsers(IsAuthenticated):
    """Custom DRF Authentication class."""

    code = 403

    def has_permission(self, request, view):
        """Return True if ENABLE_NON_USERS is true or user authenticated."""
        enu_flag = AdminFlag.objects.only("on").get(
            key=AdminFlag.FlagChoices.NON_USERS.value
        )
        if enu_flag.on:
            return True
        return super().has_permission(request, view)


class TimezoneView(GenericAPIView):
    """User info."""

    input_serializer_class = TimezoneSerializer
    serializer_class = OKSerializer

    _AUTH_USER_MODEL_TYPE = type(settings.AUTH_USER_MODEL)

    @extend_schema(request=input_serializer_class)
    def post(self, request, *args, **kwargs):
        """Get the user info for the current user."""
        serializer = self.input_serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        request.session["django_timezone"] = serializer.validated_data["timezone"]
        request.session.save()
        user = self.request.user
        if user.is_authenticated:
            UserActive.objects.update_or_create(user=user)
        serializer = self.get_serializer()
        return Response(serializer.data)


class AdminFlagsView(GenericAPIView, RetrieveModelMixin):
    """Get admin flags relevant to auth."""

    _ADMIN_FLAG_KEYS = frozenset(
        (
            AdminFlag.FlagChoices.NON_USERS.value,
            AdminFlag.FlagChoices.REGISTRATION.value,
        )
    )

    serializer_class = AuthAdminFlagsSerializer
    queryset = AdminFlag.objects.filter(key__in=_ADMIN_FLAG_KEYS).only("key", "on")

    def get_object(self):
        """Get admin flags."""
        flags = {}
        for obj in self.get_queryset():  # type: ignore
            name = CHOICES["admin"]["adminFlags"][obj.key].lower().replace(" ", "_")
            flags[name] = obj.on
        return flags

    def get(self, request, *args, **kwargs):
        """Get admin flags relevant to auth."""
        return self.retrieve(request, *args, **kwargs)
