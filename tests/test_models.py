"""Test models."""
import datetime

from django.test import TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume


class ComicTestCase(TestCase):
    """Test Comic model."""

    COMIC_PATH = "/comics/foo.cbz"
    NAME = "foo"
    DECADE = 1970
    YEAR = 1975
    MONTH = 4
    DAY = 9
    DATE = datetime.date(YEAR, MONTH, DAY)

    def setUp(self):
        """Set up for tests."""
        library = Library.objects.create(path="/comics")
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
            issue=1,
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

    def test_comic_save(self):
        """Test comic model save method."""
        comic = Comic.objects.get(path=self.COMIC_PATH)
        self.assertEqual(comic.name, self.NAME)
        self.assertEqual(comic.decade, self.DECADE)
        self.assertEqual(comic.date, self.DATE)
