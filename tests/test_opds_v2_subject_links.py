"""
OPDS v2 manifest subject links filter by their subject.

Each subject's facet link filtered on ``model name + "s"``. That spelled
``storyarcs`` and ``seriesgroups``, which are not browser filter keys
(``story_arcs``, ``series_groups``), so those links opened an unfiltered
feed.
"""

import json
import shutil
from http import HTTPStatus
from typing import Final, override
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import (
    Character,
    Comic,
    Genre,
    Imprint,
    Library,
    Location,
    Publisher,
    Series,
    SeriesGroup,
    StoryArc,
    StoryArcNumber,
    Tag,
    Team,
    Volume,
)
from codex.startup import init_admin_flags
from codex.views.browser.const import BROWSER_FILTER_KEYS
from codex.views.opds.const import OPDS_M2M_MODELS
from codex.views.opds.v2.manifest import SUBJECT_FILTER_KEYS
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
TMP_DIR: Final = tmp_dir("codex.tests.opds_v2_subject_links")
# The browser filter each subject kind's link must carry.
_EXPECTED_FILTER_KEYS: Final = frozenset(
    {
        "characters",
        "genres",
        "locations",
        "series_groups",
        "story_arcs",
        "tags",
        "teams",
    }
)


class OPDS2SubjectLinksTestCase(TestCase):
    """One comic with a subject of every kind; another series without."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        comics = []
        for name in ("Alpha", "Beta"):
            series = Series.objects.create(
                name=f"{name} Series", imprint=imprint, publisher=publisher
            )
            volume = Volume.objects.create(
                name="1", series=series, imprint=imprint, publisher=publisher
            )
            path = TMP_DIR / f"{name}.cbz"
            path.touch()
            comics.append(
                Comic.objects.create(
                    library=library,
                    path=path,
                    issue_number=1,
                    name=name,
                    publisher=publisher,
                    imprint=imprint,
                    series=series,
                    volume=volume,
                    file_type="CBZ",
                    page_count=3,
                    size=1,
                )
            )
        self.comic = comics[0]  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic.characters.add(Character.objects.create(name="Subject Character"))
        self.comic.genres.add(Genre.objects.create(name="Subject Genre"))
        self.comic.locations.add(Location.objects.create(name="Subject Location"))
        self.comic.series_groups.add(
            SeriesGroup.objects.create(name="Subject Series Group")
        )
        arc = StoryArc.objects.create(name="Subject Story Arc")
        self.comic.story_arc_numbers.add(StoryArcNumber.objects.create(story_arc=arc))
        self.comic.tags.add(Tag.objects.create(name="Subject Tag"))
        self.comic.teams.add(Team.objects.create(name="Subject Team"))
        user = User.objects.create_user(
            username="opds_subject_links_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _get(self, url: str):
        cache.clear()
        response = self.client.get(url)
        assert response.status_code == HTTPStatus.OK, (url, response.content[:300])
        return response

    def _subject_links(self) -> dict[str, str]:
        """Map each subject's name to its facet link's local url."""
        manifest = self._get(f"/opds/v2.0/c/{self.comic.pk}/1").json()
        subjects = manifest["metadata"]["subject"]
        links = {}
        for subject in subjects:
            href = urlsplit(subject["links"][0]["href"])
            links[subject["name"]] = f"{href.path}?{href.query}"
        return links

    def test_every_subject_kind_has_a_browser_filter_key(self) -> None:
        """A subject kind added to the manifest needs a browser filter key."""
        assert set(SUBJECT_FILTER_KEYS) == set(OPDS_M2M_MODELS)
        assert set(SUBJECT_FILTER_KEYS.values()) <= set(BROWSER_FILTER_KEYS)
        # This fixture gives the comic one subject of every kind.
        assert set(SUBJECT_FILTER_KEYS.values()) == _EXPECTED_FILTER_KEYS

    def test_every_subject_link_carries_a_browser_filter_key(self) -> None:
        """Each kind's link filters on its own browser filter key."""
        links = self._subject_links()
        assert len(links) == len(OPDS_M2M_MODELS), links
        filter_keys = set()
        for url in links.values():
            filters = json.loads(parse_qs(urlsplit(url).query)["filters"][0])
            assert len(filters) == 1, filters
            filter_keys |= filters.keys()
        assert filter_keys == _EXPECTED_FILTER_KEYS

    def test_every_subject_link_filters_its_feed(self) -> None:
        """Following a subject link lists only the series that has it."""
        for name, url in self._subject_links().items():
            content = self._get(url).content
            assert b"Alpha Series" in content, name
            assert b"Beta Series" not in content, name
