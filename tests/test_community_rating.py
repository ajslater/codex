"""Tests for ``Comic.community_rating`` clamping, shape, and the 0048 remap."""

import importlib
from decimal import Decimal
from pathlib import Path
from typing import override

from django.apps import apps
from django.test import TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.fields import CoercingDecimalField
from codex.models.settings import SettingsBrowser, SettingsBrowserShow

# Migration filenames start with digits, which Python's import syntax can't
# express. Use importlib so the tests exercise the actual migration helpers.
_MIGRATION_0043 = importlib.import_module(
    "codex.migrations.0043_comicbox_tagging_defaults"
)
_normalize = _MIGRATION_0043._normalize_rating  # noqa: SLF001
_MIGRATION_0048 = importlib.import_module(
    "codex.migrations.0048_community_rating_alternative_issue"
)
_remap = _MIGRATION_0048._remap  # noqa: SLF001

TMP_DIR = Path("/tmp/codex.tests.community_rating")  # noqa: S108


class CommunityRatingClampTestCase(TestCase):
    """Direct ORM writes of out-of-range community_rating get clamped."""

    COMIC_PATH = TMP_DIR / "rating.cbz"

    @override
    def setUp(self):
        """Seed minimal Library/Publisher/etc. for a Comic row."""
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.COMIC_PATH.touch()
        library = Library.objects.create(path=str(self.COMIC_PATH))
        publisher = Publisher.objects.create(name="RatingPub")
        imprint = Imprint.objects.create(name="RatingImp", publisher=publisher)
        series = Series.objects.create(
            name="RatingSeries", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="2020", series=series, imprint=imprint, publisher=publisher
        )
        self.library = library  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = publisher  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = imprint  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = series  # pyright: ignore[reportUninitializedInstanceVariable]
        self.volume = volume  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self):
        """Tear down the temp dir."""
        import shutil

        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _make_comic(self, rating: Decimal | None, count: int | None = None) -> Comic:
        return Comic.objects.create(
            library=self.library,
            path=str(self.COMIC_PATH),
            issue_number=1,
            name="rating-test",
            publisher=self.publisher,
            imprint=self.imprint,
            series=self.series,
            volume=self.volume,
            size=100,
            community_rating=rating,
            community_rating_count=count,
        )

    def test_clamps_above_max(self) -> None:
        """A direct ORM write of 99 is clamped to 5.0."""
        self._make_comic(Decimal(99))
        comic = Comic.objects.get(path=str(self.COMIC_PATH))
        assert comic.community_rating == Decimal("5.0")

    def test_in_range_passes(self) -> None:
        """A direct ORM write of 3.5 is stored unchanged (at 1 dp)."""
        self._make_comic(Decimal("3.5"))
        comic = Comic.objects.get(path=str(self.COMIC_PATH))
        assert comic.community_rating == Decimal("3.5")

    def test_null_passes(self) -> None:
        """Null community_rating survives the trip."""
        self._make_comic(None)
        comic = Comic.objects.get(path=str(self.COMIC_PATH))
        assert comic.community_rating is None
        assert comic.community_rating_count is None

    # Larger than SmallInteger's 32767 ceiling — the reason for the
    # plain PositiveIntegerField.
    BIG_COUNT = 100_000

    def test_count_round_trip(self) -> None:
        """A vote count larger than SmallInteger's ceiling survives."""
        self._make_comic(Decimal("4.2"), count=self.BIG_COUNT)
        comic = Comic.objects.get(path=str(self.COMIC_PATH))
        assert comic.community_rating_count == self.BIG_COUNT


class CoercingDecimalFieldFormulaTestCase(TestCase):
    """The internal _decimal_max formula works for any decimal_places."""

    def test_one_dp_two_digits(self) -> None:
        """decimal_places=1, max_digits=2 yields _decimal_max=9."""
        field = CoercingDecimalField(decimal_places=1, max_digits=2)
        assert field._decimal_max == Decimal(9)  # noqa: SLF001  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]

    def test_two_dp_five_digits(self) -> None:
        """decimal_places=2, max_digits=5 yields _decimal_max=999 (legacy)."""
        field = CoercingDecimalField(decimal_places=2, max_digits=5)
        assert field._decimal_max == Decimal(999)  # noqa: SLF001  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]

    def test_coerce_max_overrides(self) -> None:
        """coerce_max wins when tighter than the field ceiling."""
        field = CoercingDecimalField(  # pyright: ignore[reportCallIssue]  # ty: ignore[no-matching-overload]
            decimal_places=1,
            max_digits=2,
            coerce_max=Decimal("5.0"),
        )
        # _decimal_max is 9 (field ceiling); coerce_max is 5.0 (tighter).
        prepped = field.get_prep_value(Decimal("8.0"))
        assert prepped == Decimal("5.0")


# Each tuple: (input, expected_normalized)
MIGRATION_NORMALIZE_PARAMS = (
    (None, None),
    (Decimal(0), Decimal("0.0")),
    (Decimal("3.50"), Decimal("3.5")),  # in-range requantize
    (Decimal(5), Decimal("5.0")),
    (Decimal(8), Decimal("4.0")),  # 8/2 = 4.0
    (Decimal(10), Decimal("5.0")),  # boundary
    (Decimal(11), Decimal("0.6")),  # 11/20 = 0.55 -> 0.6
    (Decimal(90), Decimal("4.5")),
    (Decimal("94.95"), Decimal("4.7")),  # the canonical mock-data case
    (Decimal(100), Decimal("5.0")),
    (Decimal(500), Decimal("2.5")),
    (Decimal(1000), Decimal("5.0")),
)


class MigrationNormalizerTestCase(TestCase):
    """The squashed migration's rating normalizer covers the planned buckets."""

    def test_bucketing(self) -> None:
        """Each magnitude bucket lands in [0, 5] at one decimal place."""
        for value, expected in MIGRATION_NORMALIZE_PARAMS:
            assert _normalize(value) == expected, f"{value!r} -> expected {expected!r}"


class Migration0048RemapTestCase(TestCase):
    """
    0048's RunPython remaps user-settings *contents* to the new key.

    The column renames carry values automatically; order_by enum values and
    table_columns JSON dict keys do not (the 0043 lesson) — the helper
    rewrites them. Runs against live models: both surfaces still exist
    post-migration, so exercising the real helper needs no executor dance.
    """

    @staticmethod
    def _make_row(order_by: str, table_columns: dict) -> SettingsBrowser:
        # The show-flag combination is unique; share one row across cases.
        show, _ = SettingsBrowserShow.objects.get_or_create()
        return SettingsBrowser.objects.create(
            show=show, order_by=order_by, table_columns=table_columns
        )

    def test_order_by_and_table_columns_remapped(self) -> None:
        """critical_rating order_by values and JSON column keys move over."""
        remap_row = self._make_row(
            "critical_rating", {"critical_rating": True, "issue": True}
        )
        untouched_row = self._make_row("sort_name", {"issue": True})
        _remap(apps, "critical_rating", "community_rating")
        remap_row.refresh_from_db()
        untouched_row.refresh_from_db()
        assert remap_row.order_by == "community_rating"
        assert remap_row.table_columns == {"community_rating": True, "issue": True}
        assert untouched_row.order_by == "sort_name"
        assert untouched_row.table_columns == {"issue": True}

    def test_reverse_remap_mirrors(self) -> None:
        """The reverse migration maps community_rating back."""
        row = self._make_row("community_rating", {"community_rating": True})
        _remap(apps, "community_rating", "critical_rating")
        row.refresh_from_db()
        assert row.order_by == "critical_rating"
        assert row.table_columns == {"critical_rating": True}
