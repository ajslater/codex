"""Test models."""

import datetime
import shutil
from pathlib import Path

from django.test import TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume

TMP_DIR = Path("/tmp/codex.tests")  # noqa S108


class ComicTestCase(TestCase):
    """Test Comic model."""

    COMIC_PATH = TMP_DIR / "foo.cbz"
    NAME = "foo"
    DECADE = 1970
    YEAR = 1975
    MONTH = 4
    DAY = 9
    DATE = datetime.date(YEAR, MONTH, DAY)

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

    def tearDown(self):
        """Tear down tests."""
        shutil.rmtree(TMP_DIR)

    def test_comic_save(self):
        """Test comic model save method."""
        comic = Comic.objects.get(path=self.COMIC_PATH)
        assert comic.name == self.NAME
        assert comic.decade == self.DECADE
        assert comic.date == self.DATE
