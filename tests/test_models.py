"""Test models."""

import datetime
import shutil
from typing import override

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from codex.librarian.scribe.importer.const import (
    ALWAYS_UPDATE_COMIC_FIELDS,
    BULK_CREATE_COMIC_FIELDS,
    BULK_UPDATE_COMIC_FIELDS,
)
from codex.models import (
    Comic,
    CustomCover,
    FailedImport,
    Favorite,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from tests.tmp_dirs import tmp_dir

TMP_DIR = tmp_dir("codex.tests")


class ComicTestCase(TestCase):
    """Test Comic model."""

    COMIC_PATH = TMP_DIR / "foo.cbz"
    NAME = "foo"
    DECADE = 1970
    YEAR = 1975
    MONTH = 4
    DAY = 9
    DATE = datetime.date(YEAR, MONTH, DAY)

    @override
    def setUp(self):
        """Set up for tests."""
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.COMIC_PATH.touch()
        library = Library.objects.create(path=str(self.COMIC_PATH))
        publisher = Publisher.objects.create(name="FooPub")
        imprint = Imprint.objects.create(name="BarComics", publisher=publisher)
        series = Series.objects.create(
            name="Baz Patrol", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="2020", series=series, imprint=imprint, publisher=publisher
        )
        Comic.objects.create(
            library=library,
            path=self.COMIC_PATH,
            issue_number=1,
            name=ComicTestCase.NAME,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=100,
            year=self.YEAR,
            month=self.MONTH,
            day=self.DAY,
        )

    @override
    def tearDown(self):
        """Tear down tests."""
        shutil.rmtree(TMP_DIR)

    def test_comic_save(self):
        """Test comic model save method."""
        comic = Comic.objects.get(path=self.COMIC_PATH)
        assert comic.name == self.NAME
        assert comic.decade == self.DECADE
        assert comic.date == self.DATE


class FavoriteTestCase(TestCase):
    """Test Favorite model."""

    TWO_FAVORITES = 2

    @override
    def setUp(self):
        """Provision a user and one of each favorite-able row."""
        user_model = get_user_model()
        self.user = user_model.objects.create(username="favtester")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other_user = user_model.objects.create(username="favtester2")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="FavPub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="FavImp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="FavSeries",
            publisher=self.publisher,
            imprint=self.imprint,
        )

    def test_create_and_unique(self):
        """Same (user, collection, target_id) triple must not insert twice."""
        Favorite.objects.create(
            user=self.user, collection="series", target_id=self.series.pk
        )
        with transaction.atomic(), pytest.raises(IntegrityError):
            Favorite.objects.create(
                user=self.user, collection="series", target_id=self.series.pk
            )

    def test_distinct_users_share_target(self):
        """Two users may both favorite the same target."""
        Favorite.objects.create(
            user=self.user, collection="series", target_id=self.series.pk
        )
        Favorite.objects.create(
            user=self.other_user, collection="series", target_id=self.series.pk
        )
        count = Favorite.objects.filter(target_id=self.series.pk).count()
        assert count == self.TWO_FAVORITES

    def test_distinct_groups_share_target_id(self):
        """target_id may collide across groups (publisher#1 and series#1)."""
        Favorite.objects.create(user=self.user, collection="publishers", target_id=1)
        Favorite.objects.create(user=self.user, collection="series", target_id=1)
        count = Favorite.objects.filter(user=self.user).count()
        assert count == self.TWO_FAVORITES

    def test_user_delete_cascades(self):
        """Deleting a user wipes their favorites."""
        Favorite.objects.create(
            user=self.user, collection="series", target_id=self.series.pk
        )
        self.user.delete()
        assert not Favorite.objects.filter(collection="series").exists()

    def test_target_delete_cascades_via_signal(self):
        """Deleting a Series wipes pointing-at-Series favorites for all users."""
        series_pk = self.series.pk
        Favorite.objects.create(
            user=self.user, collection="series", target_id=series_pk
        )
        Favorite.objects.create(
            user=self.other_user, collection="series", target_id=series_pk
        )
        # Distractor: another user's favorite at a different group/target_id
        # (target_id=series_pk under collection="publishers") must NOT be touched.
        Favorite.objects.create(
            user=self.user, collection="publishers", target_id=series_pk
        )

        self.series.delete()

        assert not Favorite.objects.filter(
            collection="series", target_id=series_pk
        ).exists()
        assert Favorite.objects.filter(
            collection="publishers", target_id=series_pk
        ).exists()


class MissingSinceFieldTestCase(TestCase):
    """
    Pin the two silent failure modes of the ``missing_since`` column.

    Both are invisible at runtime: the wrong index declaration still
    migrates cleanly, and the wrong bulk-field membership still imports
    comics. Each would only surface as data loss much later.
    """

    def test_every_watched_path_model_has_the_field(self):
        """The field lives on the abstract base, so all four inherit it."""
        for model in (Comic, Folder, FailedImport, CustomCover):
            field = model._meta.get_field("missing_since")
            assert field.null, model.__name__
            assert field.get_default() is None, model.__name__

    def test_comic_keeps_both_of_its_indexes(self):
        """
        A subclass Meta's ``indexes`` replaces the base's, it does not merge.

        Declaring the partial index on ``WatchedPath.Meta`` would give it
        to Folder, FailedImport and CustomCover while silently skipping
        Comic -- the model that most needs it. Naming both indexes here
        catches that, and catches a later Meta edit dropping either one.
        """
        names = {index.name for index in Comic._meta.indexes}
        assert names == {"codex_comic_lib_ari_idx", "codex_comic_miss_idx"}

    def test_folder_has_its_partial_index(self):
        """Folder carries its own stamp from dirs_deleted, so it is indexed too."""
        names = {index.name for index in Folder._meta.indexes}
        assert names == {"codex_folder_miss_idx"}

    def test_both_indexes_are_partial(self):
        """
        A full index on this column would be dead weight.

        ``IS NULL`` matches ~every row and cannot be served by an index;
        the selective query is the reap's ``missing_since < cutoff``.
        """
        for model, name in (
            (Comic, "codex_comic_miss_idx"),
            (Folder, "codex_folder_miss_idx"),
        ):
            index = next(i for i in model._meta.indexes if i.name == name)
            assert index.condition is not None, model.__name__
            assert index.fields == ["missing_since"], model.__name__

    def test_the_bulk_comic_paths_never_touch_the_column(self):
        """
        The field tuples are derived from ``Comic._meta``, so it enrols itself.

        Left enrolled, ``bulk_update`` writes a freshly-constructed
        Comic's ``None`` over a live stamp on any unrelated re-import,
        and the create path's upsert does the same. The column is owned
        solely by the scanner's stamp and unstamp paths.
        """
        assert "missing_since" not in BULK_UPDATE_COMIC_FIELDS
        assert "missing_since" not in BULK_CREATE_COMIC_FIELDS
        assert "missing_since" not in ALWAYS_UPDATE_COMIC_FIELDS
