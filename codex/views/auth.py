"""Views authorization."""

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.logger.logging import get_logger
from codex.models import AdminFlag, Comic, Folder, StoryArc, UserActive
from codex.serializers.auth import TimezoneSerializer
from codex.serializers.mixins import OKSerializer

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


class TimezoneView(AuthGenericAPIView):
    """User info."""

    input_serializer_class = TimezoneSerializer
    serializer_class = OKSerializer

    def _save_timezone(self, django_timezone):
        """Save django timezone in session."""
        if not django_timezone:
            return
        session = self.request.session
        session["django_timezone"] = django_timezone
        session.save()

    def _update_user_active(self):
        """Update user activity."""
        user = self.request.user
        if user and user.is_authenticated:
            UserActive.objects.update_or_create(user=user)

    @extend_schema(request=input_serializer_class)
    def put(self, *args, **kwargs):
        """Get the user info for the current user."""
        data = self.request.data  # type: ignore
        serializer = self.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            self._save_timezone(serializer.validated_data.get("timezone"))  # type: ignore
        except Exception as exc:
            reason = f"update user timezone {exc}"
            LOG.warning(reason)

        try:
            self._update_user_active()
        except Exception as exc:
            reason = f"update user activity {exc}"
            LOG.warning(reason)

        serializer = self.get_serializer()
        return Response(serializer.data)


class GroupACLMixin:
    """Filter group ACLS for views."""

    @staticmethod
    def get_rel_prefix(model):
        """Return the relation prfiex for most fields."""
        prefix = ""
        if model != Comic:
            if model == StoryArc:
                prefix += "storyarcnumber__"
            prefix += "comic__"
        return prefix

    def get_group_acl_filter(self, model):
        """Generate the group acl filter for comics."""
        # The rel prefix
        prefix = self.get_rel_prefix(model) if model != Folder else ""
        groups_rel = f"{prefix}library__groups"

        # Libraries with no groups are always visible
        query = Q(**{f"{groups_rel}__isnull": True})

        user = self.request.user  # type: ignore

        if user and not isinstance(user, AnonymousUser):
            # Include groups are visible to users in the group
            user_filter = {f"{groups_rel}__user": user}
            exclude_rel = f"{groups_rel}__groupauth__exclude"
            exclude_query = ~Q(**user_filter, **{exclude_rel: True})
            include_query = Q(**user_filter, **{exclude_rel: False}) | ~Q(
                **{exclude_rel: False}
            )
            auth_query = exclude_query & include_query
            query |= auth_query

        return query


class AuthFilterGenericAPIView(AuthGenericAPIView, GroupACLMixin):
    """Auth Enabled GenericAPIView."""


class AuthFilterAPIView(AuthAPIView, GroupACLMixin):
    """Auth Enabled APIView."""
