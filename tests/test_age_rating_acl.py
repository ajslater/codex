"""
Tests for the per-user age-rating ACL refactor.

The ACL filter in :mod:`codex.views.auth` resolves every dynamic value
(user ceiling, AR default, anonymous flag) into two Python integers —
``max_idx`` and ``default_fits`` — that compose into a pure local-column
predicate on :attr:`Comic.age_rating_metron_index`. These tests lock
that contract in:

* per-user ceiling narrows visibility to the ranked index window
* ``UserAuth.age_rating_metron`` NULL ⇒ unrestricted
* anonymous sessions fall back to the ``AA`` flag's FK
* null/unknown-rated comics obey the ``AR`` default FK, gated by the user ceiling
* :attr:`Comic.age_rating_metron_index` is populated by :meth:`presave`
* the filter's **DB execution** is a single query over the denormalized column
* classmethod one-shot ``get_age_rating_acl_filter`` pays two tiny scalar
  lookups + one filter query = 3 total (still cache-friendly)
* the 0039 migration seeds the new ``AA`` flag and flips ``AR`` to ``Everyone``
* 0040 promotes both age-rating flags to use a typed FK
* the admin user serializer round-trips ``ageRatingMetron``
"""

import shutil
from pathlib import Path
from typing import override

from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.contrib.auth.models import AnonymousUser, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from codex.choices.admin import AdminFlagChoices
from codex.models import (
    AdminFlag,
    AgeRating,
    AgeRatingMetron,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.auth import UserAuth
from codex.views.auth import AgeRatingACLMixin

TMP_DIR = Path("/tmp/codex.tests.acl")  # noqa: S108


def _set_age_rating_flag(key: str, metron_name: str) -> None:
    """
    Point an age-rating admin flag at the given :class:`AgeRatingMetron`.

    ``AR`` / ``AA`` now store the ceiling as a typed FK, not a string,
    so tests resolve the target row and assign the pk directly.
    :meth:`update_or_create` keeps this idempotent against migration
    seed state.
    """
    metron = AgeRatingMetron.objects.get(name=metron_name)
    AdminFlag.objects.update_or_create(
        key=key,
        defaults={"age_rating_metron": metron, "value": "", "on": True},
    )


class AgeRatingACLTestCase(TestCase):
    """Exercise :class:`AgeRatingACLMixin` end-to-end against SQLite."""

    @override
    def setUp(self) -> None:
        """
        Seed a library with one comic per canonical metron rating + NULL.

        The AgeRatingMetron table is expected to be fully seeded by the
        0039 migration; we only create :class:`AgeRating` rows (one per
        name) and hook them onto :class:`Comic` instances. We also keep
        one comic with ``age_rating = NULL`` for the default-rating path
        and one tagged ``Unknown`` for the ranked-index sentinel path.
        """
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )

        def _comic_with(name_suffix: str, age_rating: AgeRating | None) -> Comic:
            path = TMP_DIR / f"{name_suffix}.cbz"
            path.touch()
            return Comic.objects.create(
                library=library,
                path=path,
                issue_number=1,
                name=name_suffix,
                publisher=publisher,
                imprint=imprint,
                series=series,
                volume=volume,
                size=1,
                age_rating=age_rating,
            )

        # One comic per ranked rating — presave() auto-links ``metron``.
        self.comics_by_rating: dict[str, Comic] = {}  # pyright: ignore[reportUninitializedInstanceVariable]
        for name in (
            MetronAgeRatingEnum.EVERYONE.value,
            MetronAgeRatingEnum.TEEN.value,
            MetronAgeRatingEnum.MATURE.value,
            MetronAgeRatingEnum.ADULT.value,
        ):
            rating = AgeRating(name=name)
            rating.presave()
            rating.save()
            self.comics_by_rating[name] = _comic_with(name.lower(), rating)

        # Null-rated comic (no AgeRating FK at all).
        self.comic_null = _comic_with("untagged", None)  # pyright: ignore[reportUninitializedInstanceVariable]
        # Unknown-rated comic (rating name exists but maps to the
        # UNRANKED metron sentinel — exercised separately from NULL).
        unknown = AgeRating(name=MetronAgeRatingEnum.UNKNOWN.value)
        unknown.presave()
        unknown.save()
        self.comic_unknown = _comic_with("unknown", unknown)  # pyright: ignore[reportUninitializedInstanceVariable]

        # Users: ``teen_user`` has a Teen ceiling, ``open_user`` has none.
        # ``UserAuth`` rows are auto-provisioned by the User ``post_save``
        # signal (see codex.signals.django_signals); we just patch the
        # ceiling on the auto-created row for ``teen_user``. ``open_user``
        # gets the default (None ⇒ unrestricted) without any extra work.
        self.teen_user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="teen",
            password="x",  # noqa: S106
        )
        teen_metron = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.TEEN.value)
        UserAuth.objects.filter(user=self.teen_user).update(
            age_rating_metron=teen_metron
        )

        self.open_user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="open",
            password="x",  # noqa: S106
        )

        # Default flag = Everyone (matches the new seed); tests that need
        # a looser or tighter default override via ``_set_flag``.
        _set_age_rating_flag(
            AdminFlagChoices.AGE_RATING_DEFAULT.value,
            MetronAgeRatingEnum.EVERYONE.value,
        )
        _set_age_rating_flag(
            AdminFlagChoices.ANONYMOUS_USER_AGE_RATING.value,
            MetronAgeRatingEnum.ADULT.value,
        )

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    # --- helpers -----------------------------------------------------

    def _visible_names(self, user) -> set[str]:
        """Resolve the ACL filter and return the visible comic names."""
        q = AgeRatingACLMixin.get_age_rating_acl_filter(Comic, user)
        return set(Comic.objects.filter(q).values_list("name", flat=True))

    # --- per-user ceiling -------------------------------------------

    def test_teen_user_sees_only_teen_and_below(self) -> None:
        """Teen ceiling → Everyone and Teen visible; Mature/Adult hidden."""
        visible = self._visible_names(self.teen_user)
        assert "everyone" in visible
        assert "teen" in visible
        assert "mature" not in visible
        assert "adult" not in visible

    def test_open_user_sees_all_ranked_comics(self) -> None:
        """NULL age_rating_metron ⇒ UNRESTRICTED_RATING_INDEX pass-through."""
        visible = self._visible_names(self.open_user)
        for tier in ("everyone", "teen", "mature", "adult"):
            assert tier in visible, f"{tier} should be visible"

    # --- null/unknown via the AR default gate ------------------------

    def test_untagged_comic_follows_ar_default_when_permissive(self) -> None:
        """AR = Everyone ⇒ null/unknown-rated comics visible to everyone."""
        _set_age_rating_flag(
            AdminFlagChoices.AGE_RATING_DEFAULT.value,
            MetronAgeRatingEnum.EVERYONE.value,
        )
        teen_visible = self._visible_names(self.teen_user)
        assert "untagged" in teen_visible
        assert "unknown" in teen_visible

    def test_untagged_comic_hidden_when_ar_exceeds_user_ceiling(self) -> None:
        """AR = Adult + Teen user ⇒ null/unknown rows fall outside the window."""
        _set_age_rating_flag(
            AdminFlagChoices.AGE_RATING_DEFAULT.value,
            MetronAgeRatingEnum.ADULT.value,
        )
        teen_visible = self._visible_names(self.teen_user)
        assert "untagged" not in teen_visible
        assert "unknown" not in teen_visible
        # Ranked comics at/below the Teen ceiling stay visible.
        assert "teen" in teen_visible
        assert "everyone" in teen_visible

    # --- anonymous flag ---------------------------------------------

    def test_anonymous_ceiling_uses_aa_flag(self) -> None:
        """Anonymous session obeys the ``AA`` flag, not a user FK."""
        _set_age_rating_flag(
            AdminFlagChoices.ANONYMOUS_USER_AGE_RATING.value,
            MetronAgeRatingEnum.EVERYONE.value,
        )
        visible = self._visible_names(AnonymousUser())
        assert "everyone" in visible
        # Anonymous ceiling at Everyone hides every stricter tier.
        assert "teen" not in visible
        assert "mature" not in visible
        assert "adult" not in visible

    # --- query-shape assertions --------------------------------------

    def test_scalar_filter_executes_as_single_query(self) -> None:
        """
        Given precomputed scalars, the ACL Q collapses to one SQL query.

        :meth:`AgeRatingACLMixin.get_age_rating_acl_filter_for` takes
        already-resolved ``max_idx`` + ``default_fits`` values and
        returns a Q that compares
        :attr:`Comic.age_rating_metron_index` directly — no subqueries,
        no joins. This is the path that view code takes per-request via
        :meth:`GroupACLMixin.get_acl_filter`: the two scalars are cached
        on the view once, then reused across every model filter, so
        each additional filter call stays at one query.
        """
        max_idx = AgeRatingACLMixin.compute_max_idx(self.teen_user)
        default_fits = AgeRatingACLMixin.compute_default_fits(max_idx)
        with CaptureQueriesContext(connection) as ctx:
            q = AgeRatingACLMixin.get_age_rating_acl_filter_for(
                Comic, max_idx, default_fits=default_fits
            )
            list(Comic.objects.filter(q).values_list("pk", flat=True))
        assert len(ctx.captured_queries) == 1, ctx.captured_queries

    def test_one_shot_classmethod_is_three_queries(self) -> None:
        """
        The one-shot ``get_age_rating_acl_filter`` pays 2 scalar lookups + 1 filter.

        The classmethod is preserved for tests and isolated callers that
        don't have a request to hang the memo on. It recomputes
        ``max_idx`` (one UserAuth lookup) and ``default_fits`` (one
        AdminFlag lookup) per call, then runs the filter query. That's
        three queries — all three are tiny and cachalot-cacheable, but
        the count is the budget a regression must stay under.
        """
        # 2 tiny scalar lookups (UserAuth, AdminFlag) + 1 filter query.
        # Bumping this budget means the ACL recompute got more expensive
        # than designed; the one-shot path is for tests, not hot code.
        max_queries = 3
        with CaptureQueriesContext(connection) as ctx:
            q = AgeRatingACLMixin.get_age_rating_acl_filter(Comic, self.teen_user)
            list(Comic.objects.filter(q).values_list("pk", flat=True))
        assert len(ctx.captured_queries) <= max_queries, ctx.captured_queries

    # --- denorm column contract --------------------------------------

    def test_presave_populates_age_rating_metron_index(self) -> None:
        """
        :meth:`Comic.presave` mirrors ``age_rating.metron.index`` locally.

        The ACL filter reads :attr:`Comic.age_rating_metron_index` directly,
        so this denorm column is the ground truth once presave has run.
        Verifies ranked, tagged-``Unknown`` (``UNRANKED_METRON_INDEX``),
        and null-rated comics each end up in the right bucket.
        """
        from codex.models.age_rating import UNRANKED_METRON_INDEX

        everyone = self.comics_by_rating[MetronAgeRatingEnum.EVERYONE.value]
        everyone.refresh_from_db()
        assert everyone.age_rating_metron_index == 0

        mature = self.comics_by_rating[MetronAgeRatingEnum.MATURE.value]
        mature.refresh_from_db()
        assert mature.age_rating_metron_index == 3  # noqa: PLR2004

        self.comic_unknown.refresh_from_db()
        assert self.comic_unknown.age_rating_metron_index == UNRANKED_METRON_INDEX

        self.comic_null.refresh_from_db()
        assert self.comic_null.age_rating_metron_index is None


class MigrationShapeTestCase(TestCase):
    """
    Migration 0039 shape assertions, post-apply.

    Django applies every migration before the test DB is handed back, so
    we can assert on the resulting schema + seeded rows without spinning
    up an executor manually.
    """

    def test_user_auth_row_exists_for_every_user(self) -> None:
        """0039 backfills UserAuth for every existing User."""
        # ``UserActive`` was renamed (not dropped+created), then 0039
        # backfills a default ``UserAuth`` row for any User missing one
        # — heals the legacy lazy-create gap so the bookmark thread's
        # activity touch is silent for everyone (the new invariant is
        # enforced going forward by a User ``post_save`` signal).
        from django.contrib.auth.models import User

        assert UserAuth.objects.count() == User.objects.count()

    def test_all_metron_ratings_seeded(self) -> None:
        """Every ``MetronAgeRatingEnum`` value gets an AgeRatingMetron row."""
        seeded = set(AgeRatingMetron.objects.values_list("name", flat=True))
        expected = {m.value for m in MetronAgeRatingEnum}
        assert expected.issubset(seeded), expected - seeded

    def test_anonymous_user_age_rating_flag_seeded_to_adult(self) -> None:
        """The ``AA`` admin flag is created with the Adult FK default."""
        flag = AdminFlag.objects.get(
            key=AdminFlagChoices.ANONYMOUS_USER_AGE_RATING.value
        )
        # 0040 backfills the FK from the 0039 ``value`` seed and clears
        # the string, so the FK is now the source of truth.
        assert flag.age_rating_metron is not None
        assert flag.age_rating_metron.name == MetronAgeRatingEnum.ADULT.value
        assert flag.value == ""

    def test_age_rating_default_flag_seeded_to_everyone(self) -> None:
        """``AR`` default flipped from Adult to Everyone in 0039 (FK form after 0040)."""
        flag = AdminFlag.objects.get(key=AdminFlagChoices.AGE_RATING_DEFAULT.value)
        assert flag.age_rating_metron is not None
        assert flag.age_rating_metron.name == MetronAgeRatingEnum.EVERYONE.value
        assert flag.value == ""


class UserSerializerRoundtripTestCase(TestCase):
    """
    Admin :class:`UserSerializer` must round-trip ``age_rating_metron``.

    This guards against the nested-auth update path regressing: the
    serializer pops ``userauth`` into a sub-dict then hands it off to
    ``_apply_userauth``, which then saves the FK. Losing the pop or the
    save would drop the field silently.
    """

    @override
    def setUp(self) -> None:
        """Create a user plus a UserAuth row."""
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="roundtrip",
            password="x",  # noqa: S106
        )
        # ``UserAuth`` is auto-provisioned by the User ``post_save`` signal
        # (see codex.signals.django_signals); fetch the auto-created row.
        # The reverse accessor ``user.userauth`` works at runtime but is
        # invisible to basedpyright, so go through the manager.
        self.userauth = UserAuth.objects.get(user=self.user)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.teen_metron = AgeRatingMetron.objects.get(  # pyright: ignore[reportUninitializedInstanceVariable]
            name=MetronAgeRatingEnum.TEEN.value
        )

    def test_update_sets_age_rating_metron(self) -> None:
        """Supplying ``age_rating_metron`` via update persists to UserAuth."""
        from codex.serializers.admin.users import UserSerializer

        serializer = UserSerializer(
            instance=self.user,
            data={"age_rating_metron": self.teen_metron.pk},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()

        self.userauth.refresh_from_db()
        # Access the related object to avoid pyright confusion with the
        # FK's implicit ``_id`` attribute.
        assert self.userauth.age_rating_metron == self.teen_metron

    def test_update_clears_age_rating_metron_with_null(self) -> None:
        """Setting the FK to NULL clears the per-user ceiling."""
        from codex.serializers.admin.users import UserSerializer

        # Start with a non-null ceiling. Django FKs narrow to ``None`` at
        # the type level when the field declares ``default=None``; the
        # runtime assignment is fine, so silence the false positive.
        self.userauth.age_rating_metron = self.teen_metron
        self.userauth.save(update_fields=["age_rating_metron"])

        serializer = UserSerializer(
            instance=self.user,
            data={"age_rating_metron": None},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()

        self.userauth.refresh_from_db()
        assert self.userauth.age_rating_metron is None


class AdminFlagSerializerRoundtripTestCase(TestCase):
    """
    :class:`AdminFlagSerializer` must round-trip ``age_rating_metron``.

    The 0040 migration promoted ``AR``/``AA`` to a typed FK. The admin
    Flags tab PATCHes ``age_rating_metron`` (a pk), so this test guards
    the flag serializer's ability to persist the FK without a regression
    back to the stringly-typed ``value`` field.
    """

    def test_update_sets_age_rating_metron_on_ar_flag(self) -> None:
        """Supplying ``age_rating_metron`` via update persists to AdminFlag."""
        from codex.serializers.admin.flags import AdminFlagSerializer

        teen_metron = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.TEEN.value)
        flag = AdminFlag.objects.get(key=AdminFlagChoices.AGE_RATING_DEFAULT.value)

        serializer = AdminFlagSerializer(
            instance=flag,
            data={"age_rating_metron": teen_metron.pk},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()

        flag.refresh_from_db()
        assert flag.age_rating_metron == teen_metron
