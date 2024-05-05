"""Views authorization."""

from types import MappingProxyType

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import AdminFlag, Comic, Folder, StoryArc, UserActive
from codex.serializers.auth import AuthAdminFlagsSerializer, TimezoneSerializer
from codex.serializers.choices import CHOICES
from codex.serializers.mixins import OKSerializer
from codex.views.const import GROUP_NAME_MAP

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


class GroupACLMixin:
    """Filter group ACLS for views."""

    ROOT_GROUP = "r"
    FOLDER_GROUP = "f"
    STORY_ARC_GROUP = "a"
    COMIC_GROUP = "c"
    GROUP_RELATION = MappingProxyType(
        {
            **GROUP_NAME_MAP,
            COMIC_GROUP: "pk",
            FOLDER_GROUP: "parent_folder",
            STORY_ARC_GROUP: "story_arc_numbers__story_arc",
        }
    )

    def get_rel_prefix(self, model):
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
