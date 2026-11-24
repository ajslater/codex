"""
OPDS v2 manifests and facets do not inherit the last feed's state.

The manifest went through the browser pipeline, so the saved OPDS
filters applied to it: after a list feed, a book not in that list got
a manifest with no reading order. A Read Filter facet on a list feed
replaced ``filters`` wholesale (the list dropped) but kept its ``title``
(the list's name). These were shelves before shelves folded into lists.
"""

import json
from typing import Final
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import Group

from codex.models import Comic, GroupAuth, Library, ReadingList
from codex.views.readinglists.entries import add_comics
from tests.test_opds_keep_reading import (
    _TEST_PASSWORD,
    _TMP_DIR,
    KeepReadingSeedTestCase,
    _group,
)

_HTTP_OK: Final = 200
_HTTP_NOT_FOUND: Final = 404
_SHELF_NAME: Final = "Want to Read"


def _manifest_url(pk: int) -> str:
    return f"/opds/v2.0/c/{pk}/1"


class OPDS2ManifestFacetTestCase(KeepReadingSeedTestCase):
    """A manifest is one visible comic; a facet narrows the current feed."""

    def _login(self) -> None:
        assert self.client.login(username=self.user.username, password=_TEST_PASSWORD)

    def _shelf_feed_url(self) -> str:
        """Return the shelf's own link from the start page, as a client follows it."""
        shelf = ReadingList.objects.create(user=self.user, name=_SHELF_NAME)
        add_comics(shelf, [self.comics[0].pk])
        group = _group(self._feed(self.client), _SHELF_NAME)
        assert group is not None
        href = group["links"][0]["href"]
        split = urlsplit(href)
        return f"{split.path}?{split.query}"

    def _get(self, url: str):
        response = self.client.get(url)
        return response, json.loads(response.content) if response.content else {}

    def test_manifest_ignores_the_last_feeds_filters(self) -> None:
        self._login()
        response, _ = self._get(self._shelf_feed_url())
        assert response.status_code == _HTTP_OK, response.content[:300]

        off_shelf = self.comics[4]
        response, manifest = self._get(_manifest_url(off_shelf.pk))

        assert response.status_code == _HTTP_OK, response.content[:300]
        assert manifest.get("readingOrder"), manifest

    def test_manifest_of_a_hidden_comic_is_404(self) -> None:
        private_dir = _TMP_DIR / "private"
        private_dir.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(private_dir))
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        library.groups.add(readers)
        path = private_dir / "hidden.cbz"
        path.touch()
        template = self.comics[0]
        hidden = Comic.objects.create(
            library=library,
            path=path,
            issue_number=99,
            name="hidden",
            publisher=template.publisher,
            imprint=template.imprint,
            series=template.series,
            volume=template.volume,
            file_type="CBZ",
            page_count=3,
            size=1,
        )
        self._login()

        response, _ = self._get(_manifest_url(hidden.pk))
        assert response.status_code == _HTTP_NOT_FOUND, response.content[:300]

    def test_manifest_of_an_unknown_comic_is_404(self) -> None:
        self._login()
        response, _ = self._get(_manifest_url(999_999))
        assert response.status_code == _HTTP_NOT_FOUND, response.content[:300]

    def test_read_filter_facet_keeps_the_list_and_drops_the_title(self) -> None:
        self._login()
        response, feed = self._get(self._shelf_feed_url())
        assert response.status_code == _HTTP_OK, response.content[:300]
        list_pk = ReadingList.objects.get(user=self.user).pk

        # The v2 feed carries its facets as navigation groups.
        facet = next(
            link
            for group in feed.get("groups", [])
            for link in group.get("navigation", []) + group.get("links", [])
            if link.get("title") == "Unread"
        )
        query = parse_qs(urlsplit(facet["href"]).query)

        filters = json.loads(query["filters"][0])
        assert filters.get("bookmark") == "UNREAD", filters
        assert filters.get("reading_lists") == [list_pk], filters
        assert "title" not in query, query
