"""Views authorization bases."""

from typing import TYPE_CHECKING

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from codex.logger.logging import get_logger
from codex.models import AdminFlag, Comic, Folder, StoryArc

if TYPE_CHECKING:
    from django.contrib.auth.models import User

LOG = get_logger(__name__)


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


class AuthMixin:
    """General Auth Policy."""

    permission_classes = (IsAuthenticatedOrEnabledNonUsers,)


class AuthAPIView(AuthMixin, APIView):
    """Auth Policy APIView."""


class AuthGenericAPIView(AuthMixin, GenericAPIView):
    """Auth Policy GenericAPIView."""


class GroupACLMixin:
    """Filter group ACLS for views."""

    @property
    def is_admin(self):
        """Is the current user an admin."""
        if self._is_admin is None:
            user: User = self.request.user  # type: ignore
            self._is_admin = user and user.is_staff
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

        q |= include_q | ~exclude_q

        return q


class AuthFilterGenericAPIView(AuthGenericAPIView, GroupACLMixin):
    """Auth Enabled GenericAPIView."""


class AuthFilterAPIView(AuthAPIView, GroupACLMixin):
    """Auth Enabled APIView."""
