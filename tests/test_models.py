"""Test models."""

import datetime as dt
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
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Shelf,
    ShelfItem,
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
    DATE = dt.date(YEAR, MONTH, DAY)

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


class ShelfTestCase(TestCase):
    """Test Shelf and ShelfItem models."""

    TWO_ITEMS = 2

    @override
    def setUp(self):
        """Provision two users with a shelf each and a shelvable row."""
        user_model = get_user_model()
        self.user = user_model.objects.create(username="shelftester")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other_user = user_model.objects.create(username="shelftester2")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.shelf = Shelf.objects.create(user=self.user, name="Want to Read")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.other_shelf = Shelf.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            user=self.other_user, name="Want to Read"
        )
        self.publisher = Publisher.objects.create(name="ShelfPub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="ShelfImp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="ShelfSeries",
            publisher=self.publisher,
            imprint=self.imprint,
        )

    def test_shelf_name_unique_per_user(self):
        """One user cannot have two shelves with the same name; two users can."""
        with transaction.atomic(), pytest.raises(IntegrityError):
            Shelf.objects.create(user=self.user, name="Want to Read")

    def test_item_unique_per_shelf(self):
        """Same (shelf, collection, target_id) triple must not insert twice."""
        ShelfItem.objects.create(
            shelf=self.shelf, collection="series", target_id=self.series.pk
        )
        with transaction.atomic(), pytest.raises(IntegrityError):
            ShelfItem.objects.create(
                shelf=self.shelf, collection="series", target_id=self.series.pk
            )

    def test_distinct_shelves_share_target(self):
        """The same target may sit on several shelves."""
        second = Shelf.objects.create(user=self.user, name="Second")
        for shelf in (self.shelf, second, self.other_shelf):
            ShelfItem.objects.create(
                shelf=shelf, collection="series", target_id=self.series.pk
            )
        count = ShelfItem.objects.filter(shelf__user=self.user).count()
        assert count == self.TWO_ITEMS

    def test_distinct_collections_share_target_id(self):
        """target_id may collide across collections (publisher#1 and series#1)."""
        ShelfItem.objects.create(shelf=self.shelf, collection="publishers", target_id=1)
        ShelfItem.objects.create(shelf=self.shelf, collection="series", target_id=1)
        assert ShelfItem.objects.filter(shelf=self.shelf).count() == self.TWO_ITEMS

    def test_user_delete_cascades(self):
        """Deleting a user wipes their shelves and items."""
        ShelfItem.objects.create(
            shelf=self.shelf, collection="series", target_id=self.series.pk
        )
        self.user.delete()
        assert not Shelf.objects.filter(pk=self.shelf.pk).exists()
        assert not ShelfItem.objects.filter(collection="series").exists()

    def test_shelf_delete_cascades(self):
        """Deleting a shelf wipes its items only."""
        for shelf in (self.shelf, self.other_shelf):
            ShelfItem.objects.create(
                shelf=shelf, collection="series", target_id=self.series.pk
            )
        self.shelf.delete()
        assert list(ShelfItem.objects.values_list("shelf_id", flat=True)) == [
            self.other_shelf.pk
        ]

    def test_target_delete_cascades_via_signal(self):
        """Deleting a Series wipes pointing-at-Series items on every shelf."""
        series_pk = self.series.pk
        for shelf in (self.shelf, self.other_shelf):
            ShelfItem.objects.create(
                shelf=shelf, collection="series", target_id=series_pk
            )
        # Distractor: the same target_id under another collection must
        # NOT be touched.
        ShelfItem.objects.create(
            shelf=self.shelf, collection="publishers", target_id=series_pk
        )

        self.series.delete()

        assert not ShelfItem.objects.filter(
            collection="series", target_id=series_pk
        ).exists()
        assert ShelfItem.objects.filter(
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
