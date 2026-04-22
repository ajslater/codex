"""Views authorization bases."""

from collections.abc import Sequence
from typing import override

from django.contrib.auth.models import AnonymousUser
from django.db.models import Exists, IntegerField, Subquery, Value
from django.db.models.functions import Coalesce
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
from codex.models.age_rating import (
    UNRANKED_METRON_INDEX,
    UNRESTRICTED_RATING_INDEX,
)
from codex.models.auth import UserAuth


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
    Per-user Metron age-rating ACL filter.

    Always applies — there is no "restriction mode" gate. For authenticated
    users, the ceiling comes from :attr:`UserAuth.age_rating_metron` (NULL
    FK ⇒ unrestricted, via :data:`UNRESTRICTED_RATING_INDEX` sentinel). For
    anonymous users, the ceiling comes from the
    :attr:`AdminFlagChoices.ANONYMOUS_USER_AGE_RATING` admin flag's
    :attr:`AdminFlag.age_rating_metron` FK.

    Null-rated comics (``Comic.age_rating is NULL``), comics whose
    :class:`AgeRating` row failed to map to a canonical metron row
    (``AgeRating.metron is NULL``), and comics tagged ``Unknown``
    (``AgeRatingMetron.index == UNRANKED_METRON_INDEX``) all inherit the
    :attr:`AdminFlagChoices.AGE_RATING_DEFAULT` flag's FK rating.

    **The returned Q resolves every value in SQL** as a single FK hop per
    flag: user ceiling and both admin-flag ratings are ``Subquery`` /
    ``Exists`` expressions over ``age_rating_metron__index`` — no
    Python-side reads, no name-matching round-trip through
    :attr:`AgeRatingMetron.name`. Python only picks which ``max_idx``
    subquery shape to use based on whether the request is authenticated.
    Admins are NOT exempt.

    Comparisons hit :attr:`AgeRatingMetron.index`, a small indexed integer
    column reached via the ``age_rating__metron`` chain. Django's LEFT
    JOIN semantics on ``__`` chains make null ``Comic.age_rating`` or
    null ``AgeRating.metron`` both satisfy ``__isnull=True``.
    """

    @staticmethod
    def _flag_rating_index_expr(flag_key: str, *, fallback: int):
        """
        Resolve an admin flag's FK to its :attr:`AgeRatingMetron.index`.

        Emits SQL roughly:
            COALESCE(
              (SELECT age_rating_metron__index FROM codex_adminflag
                 WHERE key = <flag_key> LIMIT 1),
              <fallback>
            )

        ``fallback`` applies when the flag row is missing OR its FK is
        NULL — both end the subquery in a NULL, which ``Coalesce`` swaps
        for the sentinel.
        """
        return Coalesce(
            Subquery(
                AdminFlag.objects.filter(key=flag_key).values(
                    "age_rating_metron__index"
                )[:1]
            ),
            Value(fallback),
            output_field=IntegerField(),
        )

    @classmethod
    def _max_idx_expr(cls, user):
        """
        Build the SQL expression for the user's max allowed metron index.

        Authenticated: :attr:`UserAuth.age_rating_metron__index`, coalesced to
        :data:`UNRESTRICTED_RATING_INDEX` when the FK is NULL (no per-user
        restriction).

        Anonymous: the ``ANONYMOUS_USER_AGE_RATING`` admin flag's FK
        index, coalesced to ``0`` (Everyone) when the flag is missing or
        its FK is NULL.
        """
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return cls._flag_rating_index_expr(
                AdminFlagChoices.ANONYMOUS_USER_AGE_RATING.value,
                fallback=0,
            )
        return Coalesce(
            Subquery(
                UserAuth.objects.filter(user=user).values("age_rating_metron__index")[
                    :1
                ]
            ),
            Value(UNRESTRICTED_RATING_INDEX),
            output_field=IntegerField(),
        )

    @classmethod
    def get_age_rating_acl_filter(cls, model, user) -> Q:
        """
        Build the age-rating ACL filter — single lazy expression.

        Returned shape (one Q, three SQL sub-expressions, zero Python reads):
          * ranked:      comic rating in ``[0, max_idx_expr]``
          * null/unknown: OR-gate that only fires when the
                          ``AGE_RATING_DEFAULT`` flag's FK index also fits
                          within ``max_idx_expr``.
        """
        rel = cls.get_rel_prefix(model) + "age_rating__metron"
        max_idx_expr = cls._max_idx_expr(user)

        q_ranked = Q(**{f"{rel}__index__gte": 0}) & Q(
            **{f"{rel}__index__lte": max_idx_expr}
        )
        q_null_or_unknown = Q(**{f"{rel}__isnull": True}) | Q(
            **{f"{rel}__index": UNRANKED_METRON_INDEX}
        )
        # Exists-gate: the AR flag row must exist AND its FK must point
        # at a metron row whose index fits under the user's ceiling. If
        # the FK is NULL (misconfigured flag), the ``__index__lte``
        # comparison evaluates NULL → False, so null/unknown-rated
        # comics stay hidden — the safest fallback.
        default_fits = Exists(
            AdminFlag.objects.filter(
                key=AdminFlagChoices.AGE_RATING_DEFAULT.value,
                age_rating_metron__index__lte=max_idx_expr,
            )
        )
        return q_ranked | (q_null_or_unknown & default_fits)


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
