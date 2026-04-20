"""Views authorization bases."""

from collections.abc import Sequence
from typing import override

from django.contrib.auth.models import AnonymousUser
from django.db.models.query_utils import Q
from loguru import logger
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.exceptions import NotAuthenticated
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.choices.admin import AdminFlagChoices
from codex.models import AdminFlag, Comic, Folder, StoryArc
from codex.models.admin import GroupAuth
from codex.models.age_rating import (
    DEFAULT_AGE_RATING,
    METRON_RATING_ORDER,
    PUBLIC_TIER_ALLOWED,
    UNKNOWN_VALUE,
    allowed_ratings_for,
    rating_index,
)


class IsAuthenticatedOrEnabledNonUsers(IsAuthenticated):
    """Custom DRF Authentication class."""

    code = 401

    @override
    def has_permission(self, request, view) -> bool:
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


class IsAdminMixin:
    """Expose lazy ``is_admin`` check for the current request user."""

    def init_is_admin(self) -> None:
        """Initialize the cached admin flag."""
        self._is_admin: bool | None = None  # pyright: ignore[reportUninitializedInstanceVariable]

    @property
    def is_admin(self) -> bool:
        """Is the current user an admin."""
        if self._is_admin is None:
            user = self.request.user  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            self._is_admin = bool(user and getattr(user, "is_staff", False))
        return self._is_admin


class RelPrefixMixin:
    """Compute relation prefixes for ORM traversal from arbitrary models to Comic."""

    @staticmethod
    def get_rel_prefix(model) -> str:
        """Return the relation prefix for most fields."""
        prefix = ""
        if model is Comic:
            return prefix
        if model is StoryArc:
            prefix += "storyarcnumber__"
        prefix += "comic__"
        return prefix


class GroupACLFilterMixin(RelPrefixMixin):
    """Library-group ACL filter: visibility based on group membership."""

    @classmethod
    def get_group_acl_filter(cls, model, user) -> Q:
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


class AgeRatingACLMixin(RelPrefixMixin):
    """
    Metron age-rating ACL filter.

    Age-restriction mode activates only when at least one ``GroupAuth`` row has
    a real Metron rating (``Unknown`` does not count; it is treated as null
    at filter time). Null- and ``Unknown``-rated comics inherit the
    ``AGE_RATING_DEFAULT`` admin flag value. Admins are NOT exempt.
    """

    @staticmethod
    def _age_restriction_mode_active() -> bool:
        """Return True if any group has a real (ordered) age rating set."""
        return GroupAuth.objects.filter(
            metron_age_rating__in=METRON_RATING_ORDER
        ).exists()

    @staticmethod
    def _get_default_rating() -> str:
        """Return the current AGE_RATING_DEFAULT flag value (falling back to Adult)."""
        try:
            value = (
                AdminFlag.objects.only("value")
                .get(key=AdminFlagChoices.AGE_RATING_DEFAULT.value)
                .value
            )
        except AdminFlag.DoesNotExist:
            return DEFAULT_AGE_RATING
        return value or DEFAULT_AGE_RATING

    @staticmethod
    def _allowed_ratings_for_user(user) -> frozenset[str]:
        """Return the allowed rating set for a user under the tier rules."""
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return PUBLIC_TIER_ALLOWED
        ratings = list(
            GroupAuth.objects.filter(
                group__user=user, metron_age_rating__in=METRON_RATING_ORDER
            ).values_list("metron_age_rating", flat=True)
        )
        if not ratings:
            return PUBLIC_TIER_ALLOWED
        most_restrictive = min(ratings, key=rating_index)
        return allowed_ratings_for(most_restrictive)

    @classmethod
    def get_age_rating_acl_filter(cls, model, user) -> Q:
        """Generate the age-rating acl filter for comics."""
        if not cls._age_restriction_mode_active():
            return Q()

        allowed = cls._allowed_ratings_for_user(user)
        rel = cls.get_rel_prefix(model) + "metron_age_rating"
        q = Q(**{f"{rel}__in": allowed})
        if cls._get_default_rating() in allowed:
            # Null and Unknown both inherit the default rating.
            q |= Q(**{f"{rel}__isnull": True}) | Q(**{rel: UNKNOWN_VALUE})
        return q


class GroupACLMixin(IsAdminMixin, GroupACLFilterMixin, AgeRatingACLMixin):
    """Merged ACL mixin: library-group visibility + age-rating restriction."""

    def init_group_acl(self) -> None:
        """Initialize cached properties."""
        self.init_is_admin()

    @classmethod
    def get_acl_filter(cls, model, user) -> Q:
        """Combine library-group and age-rating ACL filters."""
        return cls.get_group_acl_filter(model, user) & cls.get_age_rating_acl_filter(
            model, user
        )


class AuthFilterGenericAPIView(AuthGenericAPIView, GroupACLMixin):
    """Auth Enabled GenericAPIView."""

    def __init__(self, *args, **kwargs) -> None:
        """Iniit acl properties."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()


class AuthFilterAPIView(AuthAPIView, GroupACLMixin):
    """Auth Enabled APIView."""

    def __init__(self, *args, **kwargs) -> None:
        """Iniit acl properties."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()


class AuthToken(AuthGenericAPIView):
    """Auth Token creation and getting."""

    serializer_class = AuthTokenSerializer

    def get(self, *args, **kwargs) -> Response:
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

    def put(self, *args, **kwargs) -> Response:
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
