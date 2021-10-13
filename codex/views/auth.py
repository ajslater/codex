"""Views for browsing comic books."""
import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.views import APIView

from codex.models import AdminFlag, UserBookmark
from codex.serializers.auth import (
    RegistrationEnabledSerializer,
    TimezoneSerializer,
    UserCreateSerializer,
    UserLoginSerializer,
    UserSerializer,
)


LOG = logging.getLogger(__name__)
NULL_USER = {"pk": None, "username": None, "is_staff": False}


def set_timezone(request, serializer):
    """Set the timezone in the session."""
    request.session["django_timezone"] = serializer.validated_data["timezone"]
    request.session.save()


class IsAuthenticatedOrEnabledNonUsers(IsAuthenticated):
    """Custom DRF Authentication class."""

    def has_permission(self, request, view):
        """Return True if ENABLE_NON_USERS is true or user authenticated."""
        enu_flag = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_NON_USERS)
        if enu_flag.on:
            return True
        return super().has_permission(request, view)


class RegisterViewPermission(IsAuthenticatedOrEnabledNonUsers):
    """Custom Authentictiaon that always allows GET."""

    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def has_permission(self, request, view):
        """GET is always good."""
        if request.method in self.SAFE_METHODS:
            return True
        return super().has_permission(request, view)


class RegisterView(APIView):
    """Create a user."""

    permission_classes = [RegisterViewPermission]

    def create(self, username, password):
        """Create the user and assign the session bookmarks to the user."""
        user = User(username=username)
        user.set_password(password)
        user.save()
        session_key = self.request.session.session_key
        UserBookmark.objects.filter(session__session_key=session_key).update(user=user)
        return user

    def validate(self):
        """Validate."""
        enable_reg_on = (
            AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_REGISTRATION).on
        )
        if not enable_reg_on:
            raise PermissionDenied("Registration not enabled")
        serializer = UserCreateSerializer(data=self.request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as ex:
            LOG.warn(serializer.errors)
            raise ex
        return serializer

    def post(self, request, *args, **kwargs):
        """Register a new user."""
        serializer = self.validate()
        set_timezone(request, serializer)
        user = self.create(
            serializer.validated_data["username"], serializer.validated_data["password"]
        )
        user_serializer = UserSerializer(user)
        return Response(user_serializer.data, status=HTTP_201_CREATED)

    def get(self, request, *args, **kwargs):
        """Just return registration enabled."""
        er_flag_on = (
            AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_REGISTRATION).on
        )
        data = {"enableRegistration": er_flag_on}
        serializer = RegistrationEnabledSerializer(data)
        return Response(serializer.data)


class LoginView(APIView):
    """Login view."""

    def validate(self):
        """Validate."""
        serializer = UserLoginSerializer(data=self.request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as ex:
            LOG.warn(serializer.errors)
            raise ex
        return serializer

    def post(self, request, *args, **kwargs):
        """Authenticate and login."""
        serializer = self.validate()
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            raise AuthenticationFailed(detail="Authentication Failed")
        login(request, user)
        set_timezone(request, serializer)
        user_serializer = UserSerializer(user)
        return Response(user_serializer.data)


class UserView(APIView):
    """User info."""

    def post(self, request, *args, **kwargs):
        """Get the user info for the current user."""
        serializer = TimezoneSerializer(data=self.request.data)
        serializer.is_valid()
        set_timezone(request, serializer)

        user = self.request.user
        if not user:
            user = NULL_USER

        serializer = UserSerializer(user)
        return Response(serializer.data)


class LogoutView(APIView):
    """Logout."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Logout."""
        logout(request)
        return Response()
