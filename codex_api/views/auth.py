"""Views for browsing comic books."""
import logging

from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.views import APIView

from codex_api.models import AdminFlag
from codex_api.models import UserBookmark
from codex_api.serializers.auth import RegistrationEnabledSerializer
from codex_api.serializers.auth import UserCreateSerializer
from codex_api.serializers.auth import UserLoginSerializer
from codex_api.serializers.auth import UserSerializer


LOG = logging.getLogger(__name__)


class RegisterView(APIView):
    """Create a user."""

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
        enable_reg_on = AdminFlag.objects.get(name=AdminFlag.ENABLE_REGISTRATION).on
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
        user = self.create(
            serializer.validated_data["username"], serializer.validated_data["password"]
        )
        user_serializer = UserSerializer(user)
        return Response(user_serializer.data, status=HTTP_201_CREATED)

    def get(self, request, *args, **kwargs):
        """Just return registration enabled."""
        er_flag = AdminFlag.objects.get(name=AdminFlag.ENABLE_REGISTRATION)
        data = {"enableRegistration": er_flag.on}
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
        user_serializer = UserSerializer(user)
        return Response(user_serializer.data)


class UserView(APIView):
    """User info."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Get the user info for the current user."""
        serializer = UserSerializer(self.request.user)
        return Response(serializer.data)


class LogoutView(APIView):
    """Logout."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Logout."""
        logout(request)
        return Response()
