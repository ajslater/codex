"""
Views authorization bases.

Designed around a **per-request cache of three scalar values** — a
frozenset of visible library pks, an integer age-rating ceiling, and a
boolean default-rating-fits flag. Every view inheriting from
:class:`GroupACLMixin` resolves these once per request in
:meth:`~GroupACLMixin.init_group_acl` and reuses them across every
``get_acl_filter`` call, so the browser (which applies the filter to
7+ different models) pays at most three tiny queries for ACL
bookkeeping instead of three per model.

The resulting :class:`~django.db.models.Q` predicates are pure
index-friendly comparisons:

* Group ACL → ``library_id__in=<precomputed_pks>`` — no M2M traversal
  of ``library → groups → groupauth`` at Comic scan time; the walk
  happens once against tiny cached tables.
* Age-rating ACL → a comparison on
  :attr:`Comic.age_rating_metron_index`, the denormalized integer
  mirror of ``age_rating.metron.index``. No join through
  ``codex_agerating`` / ``codex_ageratingmetron`` for the filter; the
  composite index on ``(library_id, age_rating_metron_index)`` serves
  both halves of the ACL clause index-only.

The classmethod forms (:meth:`AgeRatingACLMixin.get_age_rating_acl_filter`,
:meth:`GroupACLFilterMixin.get_group_acl_filter`) remain as thin
wrappers for tests and one-off callers that don't have a request in
hand; they recompute every scalar from scratch per call.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, override

from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.sessions.models import Session
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
from codex.models import AdminFlag, Comic, Folder, Library, StoryArc
from codex.models.age_rating import (
    UNRANKED_METRON_INDEX,
    UNRESTRICTED_RATING_INDEX,
)
from codex.models.auth import UserAuth

if TYPE_CHECKING:
    from rest_framework.request import Request


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

    def _ensure_session_key(self) -> str | None:
        """Ensure a Django session row exists in the DB and return its key."""
        # The cookie may carry a session_key for a row that has been removed
        # from the DB (e.g. by sessions cleanup or expiry). The cached_db
        # backend serves such sessions from cache without rechecking, so
        # session.session_key alone is not safe to use as an FK target.
        if TYPE_CHECKING:
            self.request: Request  # pyright: ignore[reportUninitializedInstanceVariable]
        session = self.request.session
        if (
            session.session_key
            and not Session.objects.filter(session_key=session.session_key).exists()
        ):
            session.flush()
        if not session.session_key:
            session.save()
        return session.session_key


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

    @classmethod
    def _library_rel(cls, model) -> str:
        """
        Return the ORM path from ``model`` to its owning library's pk.

        Folder has its own ``library`` FK (inherited from
        :class:`~codex.models.paths.WatchedPath`), so it skips the
        ``comic__`` hop. Everything else — Comic, StoryArc, and the
        browser group models — reaches ``library_id`` through the Comic
        FK chain built by :meth:`get_rel_prefix`.
        """
        prefix = "" if model is Folder else cls.get_rel_prefix(model)
        return f"{prefix}library_id"


class GroupACLFilterMixin(RelPrefixMixin):
    """Library-group ACL filter: visibility based on group membership."""

    @classmethod
    def compute_visible_library_pks(cls, user) -> frozenset[int]:
        """
        Resolve the full library pk set visible to ``user``.

        Encodes the group ACL rules as Python set algebra against three
        tiny (cachalot-cached) library pk lookups:

        * ungrouped libraries — visible to everyone, authenticated or not;
        * libraries where the user belongs to at least one
          ``exclude=False`` group ("include" groups); and
        * libraries where the user belongs to at least one
          ``exclude=True`` group — these are **subtracted** from the
          include set, matching the original ORM expression
          ``include_q & ~exclude_q``.

        Anonymous / unauthenticated callers collapse to the ungrouped
        set, reproducing the classic "guests see ungrouped only"
        behaviour. The return type is a frozenset so it can be cached
        safely across ACL calls in the same request without defensive
        copying.
        """
        ungrouped = set(
            Library.objects.filter(groups__isnull=True).values_list("pk", flat=True)
        )
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return frozenset(ungrouped)
        user_groups = Group.objects.filter(user=user)
        include_pks = set(
            Library.objects.filter(
                groups__in=user_groups,
                groups__groupauth__exclude=False,
            ).values_list("pk", flat=True)
        )
        exclude_pks = set(
            Library.objects.filter(
                groups__in=user_groups,
                groups__groupauth__exclude=True,
            ).values_list("pk", flat=True)
        )
        return frozenset(ungrouped | (include_pks - exclude_pks))

    @classmethod
    def get_group_acl_filter_for(cls, model, visible_pks) -> Q:
        """Return the group ACL Q predicate given a precomputed pk set."""
        return Q(**{f"{cls._library_rel(model)}__in": tuple(visible_pks)})

    @classmethod
    def get_group_acl_filter(cls, model, user) -> Q:
        """
        One-shot classmethod form: recomputes the visible pk set per call.

        Preferred entry point for tests and isolated callers that don't
        have a request in hand. View code should route through the
        per-request cached version on :class:`GroupACLMixin` instead.
        """
        return cls.get_group_acl_filter_for(
            model, cls.compute_visible_library_pks(user)
        )


class AgeRatingACLMixin(RelPrefixMixin):
    """
    Per-user Metron age-rating ACL filter.

    The filter is built from two Python integers resolved once per request:
    ``max_idx`` (the user's rating ceiling, 0..5 or
    :data:`UNRESTRICTED_RATING_INDEX`) and ``default_fits`` (a boolean
    answering "does the ``AGE_RATING_DEFAULT`` flag's rating fit under
    ``max_idx``?"). The resulting Q compares
    :attr:`Comic.age_rating_metron_index` — a local integer column kept
    in sync by :meth:`Comic.presave` — so the age-rating clause is a
    single index-friendly predicate with no joins.

    Semantics:

    * ranked (``0 ≤ index ≤ max_idx``) → visible;
    * NULL index or ``UNRANKED_METRON_INDEX`` (tagged ``Unknown``) →
      visible only when ``default_fits`` is ``True``.

    Admins are **not** exempt — the filter applies uniformly.
    """

    @staticmethod
    def _flag_rating_index(flag_key: str, *, fallback: int) -> int:
        """
        Resolve an admin flag's FK to a Python int metron index.

        Missing flag row or NULL FK collapses to ``fallback``. Callers
        pick ``fallback`` so that the resulting int comparison degrades
        to the safest behaviour (strictest visibility for anonymous;
        permissive "unrestricted" for authenticated with no per-user
        limit; "no null/unknown visibility" for the AR default).
        """
        idx = (
            AdminFlag.objects.filter(key=flag_key)
            .values_list("age_rating_metron__index", flat=True)
            .first()
        )
        return idx if idx is not None else fallback

    @classmethod
    def compute_max_idx(cls, user) -> int:
        """
        Return the user's rating ceiling as a Python int.

        Authenticated:
          * ``UserAuth.age_rating_metron__index`` via one FK hop;
          * NULL FK ⇒ :data:`UNRESTRICTED_RATING_INDEX` — the sentinel
            lets ranked comics pass ``__lte`` without special-casing.

        Anonymous: the ``ANONYMOUS_USER_AGE_RATING`` admin flag's FK
        index, or ``0`` (Everyone) when the flag is unconfigured —
        the strictest ceiling, so a misconfigured flag never leaks
        content.
        """
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return cls._flag_rating_index(
                AdminFlagChoices.ANONYMOUS_USER_AGE_RATING.value, fallback=0
            )
        idx = (
            UserAuth.objects.filter(user=user)
            .values_list("age_rating_metron__index", flat=True)
            .first()
        )
        return idx if idx is not None else UNRESTRICTED_RATING_INDEX

    @classmethod
    def compute_default_fits(cls, max_idx: int) -> bool:
        """
        Return True iff the ``AGE_RATING_DEFAULT`` flag rating fits under ``max_idx``.

        ``fallback=-1`` biases the unconfigured-flag case toward
        invisibility: only a concrete ranked index (``0..5``) can
        satisfy ``0 <= idx <= max_idx``, so null/unknown-rated comics
        are hidden rather than accidentally leaked when the admin
        deletes the flag row or its FK target.
        """
        idx = cls._flag_rating_index(
            AdminFlagChoices.AGE_RATING_DEFAULT.value, fallback=-1
        )
        return 0 <= idx <= max_idx

    @classmethod
    def get_age_rating_acl_filter_for(
        cls, model, max_idx: int, *, default_fits: bool
    ) -> Q:
        """Return the age-rating ACL Q given precomputed scalars."""
        rel = cls.get_rel_prefix(model) + "age_rating_metron_index"
        q_ranked = Q(**{f"{rel}__gte": 0}) & Q(**{f"{rel}__lte": max_idx})
        if not default_fits:
            return q_ranked
        # ``default_fits`` ⇒ null- and Unknown-rated comics inherit the AR
        # default and pass the user's ceiling. The ``isnull`` clause
        # covers both "comic has no age_rating FK" and "age_rating has
        # no metron FK"; ``UNRANKED_METRON_INDEX`` (-1) covers the
        # tagged-as-Unknown case.
        q_null_or_unknown = Q(**{f"{rel}__isnull": True}) | Q(
            **{rel: UNRANKED_METRON_INDEX}
        )
        return q_ranked | q_null_or_unknown

    @classmethod
    def get_age_rating_acl_filter(cls, model, user) -> Q:
        """
        One-shot classmethod form: recomputes max_idx + default_fits per call.

        Preferred entry point for tests and isolated callers; view code
        should route through :meth:`GroupACLMixin.get_acl_filter` so the
        two integer scalars are resolved once per request instead of
        once per model filter.
        """
        max_idx = cls.compute_max_idx(user)
        default_fits = cls.compute_default_fits(max_idx)
        return cls.get_age_rating_acl_filter_for(
            model, max_idx, default_fits=default_fits
        )


class GroupACLMixin(IsAdminMixin, GroupACLFilterMixin, AgeRatingACLMixin):
    """
    Merged ACL mixin: library-group visibility + age-rating restriction.

    Adds a per-request cache over the scalar inputs to both sub-filters
    so that a browser request that applies the ACL to 7+ models incurs
    exactly three bookkeeping queries total instead of three-per-model.
    """

    def init_group_acl(self) -> None:
        """Initialize per-request cached scalars."""
        self.init_is_admin()
        # Lazily populated on first access via ``get_visible_library_pks``
        # / ``get_max_idx`` / ``get_default_fits``. Each is populated at
        # most once per request; subsequent ``get_acl_filter`` calls for
        # other models reuse the cached value.
        self._cached_visible_library_pks: frozenset[int] | None = None  # pyright: ignore[reportUninitializedInstanceVariable]
        self._cached_max_idx: int | None = None  # pyright: ignore[reportUninitializedInstanceVariable]
        self._cached_default_fits: bool | None = None  # pyright: ignore[reportUninitializedInstanceVariable]

    def get_visible_library_pks(self, user) -> frozenset[int]:
        """Return the per-request cached visible library pk set."""
        if self._cached_visible_library_pks is None:
            self._cached_visible_library_pks = self.compute_visible_library_pks(user)
        return self._cached_visible_library_pks

    def get_max_idx(self, user) -> int:
        """Return the per-request cached integer rating ceiling."""
        if self._cached_max_idx is None:
            self._cached_max_idx = self.compute_max_idx(user)
        return self._cached_max_idx

    def get_default_fits(self, user) -> bool:
        """Return the per-request cached default-rating-fits flag."""
        if self._cached_default_fits is None:
            self._cached_default_fits = self.compute_default_fits(
                self.get_max_idx(user)
            )
        return self._cached_default_fits

    def get_acl_filter(self, model, user) -> Q:
        """
        Combine library-group and age-rating ACL filters.

        Pulls all three scalar inputs out of the per-request cache,
        then composes two dead-simple Qs against local columns:
        ``library_id__in=<pks>`` and either
        ``age_rating_metron_index__lte=<max_idx>`` or an OR'd
        null/unknown clause gated by ``default_fits``.
        """
        return self.get_group_acl_filter_for(
            model, self.get_visible_library_pks(user)
        ) & self.get_age_rating_acl_filter_for(
            model, self.get_max_idx(user), default_fits=self.get_default_fits(user)
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
