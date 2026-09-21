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

:class:`ComicACL` packages the same three scalars for callers that also
need the ACL in **raw SQL** — the table view's correlated intersection
subqueries, which have no queryset to filter. One definition, two
spellings, so they cannot drift apart.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.sessions.models import Session
from django.db.models.query_utils import Q
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from loguru import logger
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.exceptions import NotAuthenticated
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from codex.choices.admin import AdminFlagChoices
from codex.collection import Collection  # not django.contrib.auth Group
from codex.models import AdminFlag, Comic, Folder, Library, StoryArc
from codex.models.age_rating import (
    UNRANKED_METRON_INDEX,
    UNRESTRICTED_RATING_INDEX,
)
from codex.models.auth import UserAuth
from codex.serializers.auth import ProfileUpdateSerializer, UserSerializer
from codex.views.envelope import EnvelopeJSONRenderer as _EnvelopeJSONRenderer

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
    """
    General Auth Policy + URL kwarg translation + default renderer.

    The browser URL scheme uses a plural-English ``collection``
    segment and an optional comma-separated ``parentIds`` segment;
    underneath, the view bodies consume engine kwargs
    (``collection`` value + ``pks`` tuple). :meth:`initial` normalizes
    the URL kwargs before the view body runs.

    ``renderer_classes`` defaults to the camelCase envelope renderer.
    Endpoints that ship binary (cover, page) or JSON:API (admin
    resources) override.
    """

    # Set by views that take ``?page=N`` as a query param (browser
    # list view). The translate step uses it to coerce ``page`` out
    # of the GET dict when the URL pattern doesn't carry it.
    requires_page: bool = False

    permission_classes: Sequence[type[BasePermission]] = (
        IsAuthenticatedOrEnabledNonUsers,
    )
    renderer_classes = (_EnvelopeJSONRenderer,)

    def initial(self, request, *args, **kwargs):
        """
        Translate browser-collection URL kwargs before auth dispatch.

        No-op on non-collection URLs (the ``collection`` kwarg isn't
        present). Also a no-op for the OPDS routes that supply engine
        kwargs directly via URL-pattern defaults — those carry ``pks``
        already, so the ``"pks" not in kwargs`` guard tells a raw browse
        URL (``collection`` segment, no ``pks`` yet) apart from one whose
        engine kwargs are already in place. Routes the request through
        DRF's standard ``initial`` chain after rewriting.
        """
        kwargs = self.kwargs  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]
        if "collection" in kwargs and "pks" not in kwargs:
            self._translate_browser_kwargs(request)
        super().initial(request, *args, **kwargs)  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]

    def _translate_browser_kwargs(self, request) -> None:
        """
        Normalize ``{collection, parent_ids}`` URL kwargs → engine ``{collection, pks}``.

        The engine speaks the collection vocabulary now, so the collection
        segment *is* the engine collection value — no char translation.
        ``/browse/publishers`` with no parent IDs is the synthetic ``ROOT``
        (lists the top collection); everything else is the named collection.
        The optional ``parent_ids`` segment becomes the engine ``pks`` tuple.
        ``page`` is pulled out of the GET dict when :attr:`requires_page` is set.
        """
        kwargs = self.kwargs  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]
        collection = kwargs.pop("collection")
        parent_ids = kwargs.pop("parent_ids", None)
        if collection == Collection.PUBLISHER and parent_ids is None:
            kwargs["collection"] = Collection.ROOT
        else:
            kwargs["collection"] = collection
        kwargs["pks"] = tuple(parent_ids) if parent_ids else ()
        if self.requires_page and "page" not in kwargs:
            try:
                kwargs["page"] = int(request.GET.get("page", 1))
            except (TypeError, ValueError):
                kwargs["page"] = 1

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

    # Class-level default doubles as the unmemoized sentinel; the
    # mixin no longer needs ``init_is_admin`` to set it before use.
    _is_admin: bool | None = None

    if TYPE_CHECKING:
        # ``self.request`` is supplied by the DRF view base class
        # at dispatch; declare the attribute for the mixin so the
        # property body type-checks without requiring a parent.
        request: Request  # pyright: ignore[reportUninitializedInstanceVariable]

    def init_is_admin(self) -> None:
        """Initialize the cached admin flag."""
        self._is_admin = None

    @property
    def is_admin(self) -> bool:
        """Is the current user an admin."""
        if self._is_admin is None:
            user = self.request.user
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
        browser collection models — reaches ``library_id`` through the Comic
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


@dataclass(frozen=True, slots=True)
class ComicACL:
    """
    The comic-visibility ACL as data, with two spellings of one definition.

    The browser's table mode builds collection-row sort keys from
    *correlated raw SQL* subqueries. Those have no queryset to hang a
    :class:`~django.db.models.Q` on, so the same predicate has to exist
    in SQL as well — and two hand-written copies drift. Instead the
    ACL's three scalars live here once and both spellings derive from
    them:

    * :meth:`q` — the ORM form, in any model's relation prefix, composed
      from the very same classmethods :meth:`GroupACLMixin.get_acl_filter`
      uses.
    * :meth:`sql` — a raw-SQL fragment for a comic table alias, plus the
      values to bind to it. Library pks are **parameters**, never
      interpolated into the statement.

    The pending-delete (``missing_since``) clause is deliberately *not*
    part of this object. The intersection queries exclude scanner-stamped
    comics unconditionally, with no staff exemption; folding the
    staff-aware clause in here would apply one rule to a cell's numerator
    and another to its denominator.
    """

    library_pks: tuple[int, ...]
    max_idx: int
    default_fits: bool

    @classmethod
    def for_user(cls, user) -> "ComicACL":
        """
        One-shot form: resolve every scalar from scratch for ``user``.

        Preferred by tests and isolated callers. View code should use
        :meth:`GroupACLMixin.get_comic_acl`, which reads the per-request
        cache instead of re-querying.
        """
        max_idx = AgeRatingACLMixin.compute_max_idx(user)
        return cls(
            library_pks=cls.order_pks(
                GroupACLFilterMixin.compute_visible_library_pks(user)
            ),
            max_idx=max_idx,
            default_fits=AgeRatingACLMixin.compute_default_fits(max_idx),
        )

    @staticmethod
    def order_pks(visible_pks) -> tuple[int, ...]:
        """Freeze a visible-library pk set into a deterministic tuple."""
        # Deterministic order matters: the pks become positional bind
        # parameters, and a stable statement string is what lets SQLite
        # reuse its prepared-statement cache across requests.
        return tuple(sorted(visible_pks))

    def q(self, model) -> Q:
        """Return the ORM spelling, relative to ``model``'s Comic relation."""
        return GroupACLFilterMixin.get_group_acl_filter_for(
            model, self.library_pks
        ) & AgeRatingACLMixin.get_age_rating_acl_filter_for(
            model, self.max_idx, default_fits=self.default_fits
        )

    def sql(self, alias: str) -> tuple[str, tuple[int, ...]]:
        """
        Return the raw-SQL spelling for a comic table ``alias`` + its parameters.

        For **correlated subqueries only**, where the collection FK the
        subquery correlates on must remain the access path and this ACL
        is merely a filter over that slice. Hence the unary ``+`` on
        ``library_id``: SQLite's documented no-op operator that
        disqualifies a term from index use. Without it the planner
        prefers ``codex_comic_lib_ari_idx`` over the collection FK index
        and each correlated evaluation scans every comic in every
        visible library instead of the handful in one collection —
        measured 4-6x slower on a 1000-comic single-library fixture, and
        it grows with the library, not the page.

        ``alias`` is always a module-private literal (``c`` / ``c2``) —
        it never carries a request value. Everything else rides in the
        returned tuple as ``%s`` parameters.
        """
        if not self.library_pks:
            # Nothing is visible. ``IN ()`` is a SQLite-only extension;
            # a false literal says the same thing without depending on it.
            return "0", ()
        rel = f"{alias}.age_rating_metron_index"
        ranked = f"({rel} >= 0 AND {rel} <= %s)"
        params: list[int] = [*self.library_pks, self.max_idx]
        if self.default_fits:
            ranked += f" OR {rel} IS NULL OR {rel} = %s"
            params.append(UNRANKED_METRON_INDEX)
        placeholders = ", ".join(["%s"] * len(self.library_pks))
        # ``age_rating_metron_index`` needs no such guard: it is only ever
        # the second column of that same composite index, unusable once
        # the leading column is out.
        return (
            f"(+{alias}.library_id IN ({placeholders}) AND ({ranked}))",
            tuple(params),
        )


class MissingACLFilterMixin(RelPrefixMixin):
    """
    Pending-delete (``missing_since``) visibility filter.

    A row whose path a scan could not find is kept for a retention
    window instead of being deleted, so its bookmarks survive a
    filesystem outage. It is hidden from ordinary users for that window
    and stays visible to staff, who are the only ones who can act on it.
    """

    @classmethod
    def get_missing_acl_filter(cls, model, user) -> Q:
        """Hide scanner-stamped rows from non-staff users."""
        if user.is_staff:
            # Not ``getattr(user, "is_staff", False)``: AnonymousUser
            # defines ``is_staff = False`` as a class attribute, so the
            # default would never be exercised and would only mislead.
            return Q()
        # Comic owns the column outright; the collection models reach it
        # through the same relation prefix the group ACL uses.
        q = Q(**{f"{cls.get_rel_prefix(model)}missing_since__isnull": True})
        if model is Folder:
            # ``get_rel_prefix(Folder)`` is the ancestor-inclusive
            # ``comic__`` m2m, so the clause above means "has at least
            # one live descendant comic". A Folder also carries its OWN
            # stamp from dirs_deleted, so it needs the self clause too --
            # the same asymmetry ``_library_rel`` already encodes.
            q &= Q(missing_since__isnull=True)
        return q


class GroupACLMixin(
    IsAdminMixin, GroupACLFilterMixin, AgeRatingACLMixin, MissingACLFilterMixin
):
    """
    Merged ACL mixin: library-group visibility + age-rating restriction.

    Adds a per-request cache over the scalar inputs to both sub-filters
    so that a browser request that applies the ACL to 7+ models incurs
    exactly three bookkeeping queries total instead of three-per-model.
    """

    # Class-level defaults double as the unmemoized sentinels.
    # Lazily populated on first access via ``get_visible_library_pks``
    # / ``get_max_idx`` / ``get_default_fits``. Each is populated at
    # most once per request; subsequent ``get_acl_filter`` calls for
    # other models reuse the cached value. ``init_group_acl`` resets
    # them between requests.
    _cached_visible_library_pks: frozenset[int] | None = None
    _cached_max_idx: int | None = None
    _cached_default_fits: bool | None = None

    def init_group_acl(self) -> None:
        """Initialize per-request cached scalars."""
        self.init_is_admin()
        self._cached_visible_library_pks = None
        self._cached_max_idx = None
        self._cached_default_fits = None

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

    def get_comic_acl(self, user) -> ComicACL:
        """
        Return the request's comic-visibility ACL as a value object.

        Same three cached scalars :meth:`get_acl_filter` composes, handed
        to callers that need the ACL in raw SQL as well as in the ORM —
        the table view's correlated intersection subqueries.
        """
        return ComicACL(
            library_pks=ComicACL.order_pks(self.get_visible_library_pks(user)),
            max_idx=self.get_max_idx(user),
            default_fits=self.get_default_fits(user),
        )

    def get_acl_filter(self, model, user, *, include_missing: bool = False) -> Q:
        """
        Combine library-group, age-rating and pending-delete ACL filters.

        Pulls all three scalar inputs out of the per-request cache,
        then composes two dead-simple Qs against local columns:
        ``library_id__in=<pks>`` and either
        ``age_rating_metron_index__lte=<max_idx>`` or an OR'd
        null/unknown clause gated by ``default_fits``.

        ``include_missing`` keeps scanner-stamped rows in the queryset.
        Writes use it so a position recorded during an outage still
        lands, and the reader uses it so an open book is not yanked
        mid-read. Read-only listings must not.
        """
        acl_filter = self.get_group_acl_filter_for(
            model, self.get_visible_library_pks(user)
        ) & self.get_age_rating_acl_filter_for(
            model, self.get_max_idx(user), default_fits=self.get_default_fits(user)
        )
        if not include_missing:
            acl_filter &= self.get_missing_acl_filter(model, user)
        return acl_filter


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
            logger.info(f"Auth Token created for user {user}")
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
        logger.info(f"Auth Token updated for user {user}")
        data = {"token": token.key}
        return Response(data)


@method_decorator(ensure_csrf_cookie, name="get")
class CSRFView(AuthAPIView):
    """
    ``GET /api/v4/auth/csrf`` — bootstrap the CSRF cookie.

    The ``ensure_csrf_cookie`` decorator forces Django to set the
    cookie on the response; the body just confirms the token value
    so a client can ferry it as a header on the next mutating
    request without waiting for a second round trip.
    """

    permission_classes = ()

    def get(self, request) -> Response:
        """Return the active CSRF token; cookie is set as a side effect."""
        return Response({"csrfToken": get_token(request)})


def user_payload(user) -> dict | None:
    """
    Serialize the public user shape, or ``None`` for anonymous sessions.

    Shared by :class:`ProfileView` and the composite
    :class:`~codex.views.session.SessionView` so the
    ``{id, username, email, is_staff, is_superuser}`` shape stays in
    one place.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return {
        "id": user.pk,
        "username": user.get_username(),
        "email": getattr(user, "email", "") or "",
        "is_staff": bool(getattr(user, "is_staff", False)),
        "is_superuser": bool(getattr(user, "is_superuser", False)),
    }


class ProfileView(AuthAPIView):
    """``GET`` and ``PATCH /api/v4/auth/profile`` — current user."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs) -> Response:
        """Return the authenticated user's profile."""
        if not getattr(request.user, "is_authenticated", False):
            raise NotAuthenticated
        data = UserSerializer(user_payload(request.user)).data
        return Response(data)

    def patch(self, request, *args, **kwargs) -> Response:
        """
        Apply a partial profile update.

        Accepts ``username`` (unless remote-user auth owns identity),
        ``email`` (blank → cleared), and ``timezone`` (stored on the
        session, same as the v3 timezone endpoint).
        """
        if not getattr(request.user, "is_authenticated", False):
            raise NotAuthenticated
        serializer = ProfileUpdateSerializer(
            data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        user = request.user
        user_model = get_user_model()
        updated_fields: list[str] = []
        username = validated.get("username")
        if username and not settings.AUTH_REMOTE_USER:
            username_field = getattr(user_model, "USERNAME_FIELD", "username")
            setattr(user, username_field, username)
            updated_fields.append(username_field)
        if "email" in validated:
            user.email = validated["email"]
            updated_fields.append("email")
        if updated_fields:
            user.save(update_fields=updated_fields)

        timezone = validated.get("timezone")
        if timezone:
            session = request.session
            session["django_timezone"] = timezone
            session.save()

        data = UserSerializer(user_payload(user)).data
        return Response(data)
