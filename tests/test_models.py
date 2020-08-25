from django.test import TestCase

from codex.models import Comic
from codex.models import Imprint
from codex.models import Library
from codex.models import Publisher
from codex.models import Series
from codex.models import Volume


class ComicTestCase(TestCase):
    COMIC_PATH = "/comics/foo.cbz"

    def setUp(self):
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
            title="foo",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=100,
        )

    def test_comic_assign(self):
        foo = Comic.objects.get(path=self.COMIC_PATH)
        self.assertEqual(foo.title, foo.display_name)
