"""Views authorization bases."""

from collections.abc import Sequence

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from loguru import logger
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.exceptions import NotAuthenticated
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from typing_extensions import override

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag, Comic, Folder, StoryArc


class IsAuthenticatedOrEnabledNonUsers(IsAuthenticated):
    """Custom DRF Authentication class."""

    code = 401

    @override
    def has_permission(self, request, view):
        """Return True if ENABLE_NON_USERS is true or user authenticated."""
        enu_flag = AdminFlag.objects.only("on").get(
            key=AdminFlagChoices.NON_USERS.value
        )
        if enu_flag.on:
            return True
        return super().has_permission(request, view)


class AuthMixin:
    """General Auth Policy."""

    permission_classes: Sequence[type[BasePermission]] = (
        IsAuthenticatedOrEnabledNonUsers,
    )


class AuthAPIView(AuthMixin, APIView):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Auth Policy APIView."""


class AuthGenericAPIView(AuthMixin, GenericAPIView):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Auth Policy GenericAPIView."""


class GroupACLMixin:
    """Filter group mixin for views and threads."""

    def init_group_acl(self):
        """Initialize properties."""
        self._is_admin: bool | None = None  # pyright: ignore[reportUninitializedInstanceVariable]

    @property
    def is_admin(self):
        """Is the current user an admin."""
        if self._is_admin is None:
            user = self.request.user  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            self._is_admin = user and getattr(user, "is_staff", False)
        return self._is_admin

    @staticmethod
    def get_rel_prefix(model):
        """Return the relation prefix for most fields."""
        prefix = ""
        if model is Comic:
            return prefix
        if model is StoryArc:
            prefix += "storyarcnumber__"
        prefix += "comic__"
        return prefix

    @classmethod
    def get_group_acl_filter(cls, model, user):
        """Generate the group acl filter for comics."""
        # The rel prefix
        groups_rel = cls.get_rel_prefix(model) if model is not Folder else ""
        groups_rel += "library__groups"

        # Libraries in no groups are visible to everyone
        ungrouped_filter = {f"{groups_rel}__isnull": True}
        q = Q(**ungrouped_filter)

        if not user or isinstance(user, AnonymousUser):
            return q
        # If logged in, see which libraries are now visible.

        user_filter = {f"{groups_rel}__user": user}
        exclude_rel = f"{groups_rel}__groupauth__exclude"

        # Include groups are visible to users in the group
        include_filter = {exclude_rel: False}
        include_filter.update(user_filter)
        include_q = Q(**include_filter)

        # Exclude groups are visible to users NOT in the group
        exclude_filter = {exclude_rel: True}
        exclude_filter.update(user_filter)
        exclude_q = Q(**exclude_filter)

        q |= include_q & ~exclude_q

        return q


class AuthFilterGenericAPIView(AuthGenericAPIView, GroupACLMixin):
    """Auth Enabled GenericAPIView."""

    def __init__(self, *args, **kwargs):
        """Iniit acl properties."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()


class AuthFilterAPIView(AuthAPIView, GroupACLMixin):
    """Auth Enabled APIView."""

    def __init__(self, *args, **kwargs):
        """Iniit acl properties."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()


class AuthToken(AuthGenericAPIView):
    """Auth Token creation and getting."""

    serializer_class = AuthTokenSerializer

    def get(self, *args, **kwargs):
        """Get auth token."""
        user = self.request.user
        if not user:
            reason = "Not an authenticated user."
            raise NotAuthenticated(detail=reason)

        token, created = Token.objects.get_or_create(user=user)
        if created:
            logger.info("Auth Token created for user {self.user}")
        data = {"token": token.key}

        return Response(data)

    def put(self, *args, **kwargs):
        """Reset auth token for user."""
        user = self.request.user
        if not user:
            reason = "Not an authenticated user."
            raise NotAuthenticated(detail=reason)

        Token.objects.filter(user=user).delete()
        token, _ = Token.objects.get_or_create(user=user)
        logger.info("Auth Token updated for user {self.user}")
        data = {"token": token.key}
        return Response(data)
