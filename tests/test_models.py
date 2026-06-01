"""Test models."""

import datetime
import shutil
from pathlib import Path
from typing import override

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from codex.models import Comic, Favorite, Imprint, Library, Publisher, Series, Volume

TMP_DIR = Path("/tmp/codex.tests")  # noqa: S108


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
        """Same (user, group, target_id) triple must not insert twice."""
        Favorite.objects.create(
            user=self.user, group="series", target_id=self.series.pk
        )
        with transaction.atomic(), pytest.raises(IntegrityError):
            Favorite.objects.create(
                user=self.user, group="series", target_id=self.series.pk
            )

    def test_distinct_users_share_target(self):
        """Two users may both favorite the same target."""
        Favorite.objects.create(
            user=self.user, group="series", target_id=self.series.pk
        )
        Favorite.objects.create(
            user=self.other_user, group="series", target_id=self.series.pk
        )
        count = Favorite.objects.filter(target_id=self.series.pk).count()
        assert count == self.TWO_FAVORITES

    def test_distinct_groups_share_target_id(self):
        """target_id may collide across groups (publisher#1 and series#1)."""
        Favorite.objects.create(user=self.user, group="publishers", target_id=1)
        Favorite.objects.create(user=self.user, group="series", target_id=1)
        count = Favorite.objects.filter(user=self.user).count()
        assert count == self.TWO_FAVORITES

    def test_user_delete_cascades(self):
        """Deleting a user wipes their favorites."""
        Favorite.objects.create(
            user=self.user, group="series", target_id=self.series.pk
        )
        self.user.delete()
        assert not Favorite.objects.filter(group="series").exists()

    def test_target_delete_cascades_via_signal(self):
        """Deleting a Series wipes pointing-at-Series favorites for all users."""
        series_pk = self.series.pk
        Favorite.objects.create(user=self.user, group="series", target_id=series_pk)
        Favorite.objects.create(
            user=self.other_user, group="series", target_id=series_pk
        )
        # Distractor: another user's favorite at a different group/target_id
        # (target_id=series_pk under group="publishers") must NOT be touched.
        Favorite.objects.create(user=self.user, group="publishers", target_id=series_pk)

        self.series.delete()

        assert not Favorite.objects.filter(group="series", target_id=series_pk).exists()
        assert Favorite.objects.filter(group="publishers", target_id=series_pk).exists()
