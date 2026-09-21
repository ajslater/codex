"""
End-to-end breadcrumb resolution.

Breadcrumbs walk the FK parent hierarchy and emit one crumb per level.
After the collection value-flip, ``self.kwargs["group"]`` is a collection
value (``"volumes"``), so the parent-chain map and the root crumb must be
keyed/built with ``Group`` members — otherwise the chain lookup misses and
nested-collection breadcrumbs collapse to just ``[root, current]``. These pin the
full chain + the collection wire shape.

``HiddenLibraryBreadcrumbsTestCase`` pins the other half: the crumb pks
come straight off the route, so the name lookup needs the *whole* ACL and
not just the pending-delete clause. With only the latter, a hand-typed url
answered 200 and named a publisher, imprint, series, volume and folder out
of a library the user is not in a group for.
"""

import shutil
from typing import Final, override

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import Comic, Folder, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_TMP_DIR: Final = Path("/tmp/codex.tests.breadcrumbs")  # noqa: S108
_VISIBLE_DIR: Final = Path("/tmp/codex.tests.breadcrumbs.visible")  # noqa: S108
_HIDDEN_DIR: Final = Path("/tmp/codex.tests.breadcrumbs.hidden")  # noqa: S108
_HIDDEN_LABEL: Final = "Secret"
# Every name a hidden library contributes, as it would appear on the wire.
# The volume is deliberately left out: its name is a bare year, which is
# too common a substring to assert on.
_SECRET_NAMES: Final = frozenset(
    {
        f"{_HIDDEN_LABEL} Publisher",
        f"{_HIDDEN_LABEL} Imprint",
        f"{_HIDDEN_LABEL} Series",
        f"{_HIDDEN_LABEL} Folder",
        _HIDDEN_DIR.name,
    }
)


def _v4(response):
    body = response.json()
    return body["data"] if isinstance(body, dict) and "data" in body else body


def _seed_library(tmp_dir: Path, label: str) -> dict:
    """Create one library holding a full hierarchy and a nested folder."""
    child_dir = tmp_dir / f"{label} Folder"
    child_dir.mkdir(parents=True, exist_ok=True)
    library = Library.objects.create(path=str(tmp_dir))
    publisher = Publisher.objects.create(name=f"{label} Publisher")
    imprint = Imprint.objects.create(name=f"{label} Imprint", publisher=publisher)
    series = Series.objects.create(
        name=f"{label} Series", imprint=imprint, publisher=publisher
    )
    volume = Volume.objects.create(
        name="1999", series=series, imprint=imprint, publisher=publisher
    )
    root_folder = Folder.objects.create(
        library=library, path=str(tmp_dir), name=tmp_dir.name
    )
    folder = Folder.objects.create(
        library=library,
        path=str(child_dir),
        name=child_dir.name,
        parent_folder=root_folder,
    )
    path = child_dir / "c1.cbz"
    path.touch()
    comic = Comic.objects.create(
        library=library,
        path=path,
        issue_number=1,
        name=f"{label} Comic",
        publisher=publisher,
        imprint=imprint,
        series=series,
        volume=volume,
        parent_folder=folder,
        size=42,
        page_count=20,
    )
    comic.folders.add(root_folder, folder)
    return {
        "library": library,
        "series": series,
        "volume": volume,
        "folder": folder,
    }


class BreadcrumbsTestCase(TestCase):
    """Browser breadcrumb resolution across the collection hierarchy."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(_TMP_DIR))
        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="Imp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=self.imprint, publisher=self.publisher
        )
        self.volume = Volume.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="2024",
            series=self.series,
            imprint=self.imprint,
            publisher=self.publisher,
        )
        path = _TMP_DIR / "c1.cbz"
        path.touch()
        Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name="C1",
            publisher=self.publisher,
            imprint=self.imprint,
            series=self.series,
            volume=self.volume,
            size=42,
            year=2024,
            page_count=20,
        )
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="breadcrumbs_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _show_full_hierarchy(self) -> None:
        """
        Enable every browse group with the shallowest top collection.

        ``top_collection="publishers"`` keeps publishers/imprints/series/volumes all
        in the valid nav set, so drilling down to a volume produces the full
        ancestor chain. (A deeper top collection would correctly *prune* the levels
        above it — root would list volumes directly.)
        """
        response = self.client.patch(
            "/api/v4/browse/publishers/settings",
            data=(
                '{"topCollection": "publishers", "show": {"publishers": true,'
                ' "imprints": true, "series": true, "volumes": true}}'
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _breadcrumbs(self, url: str) -> list[dict]:
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)["breadcrumbs"]

    def test_root_breadcrumbs_is_single_crumb(self) -> None:
        """Browsing the root publishers list yields just the root crumb."""
        crumbs = self._breadcrumbs("/api/v4/browse/publishers?page=1")
        assert len(crumbs) == 1
        assert crumbs[0]["collection"] == "publishers"
        assert crumbs[0]["parentIds"] == []
        # The redundant legacy group/pks dialect is gone.
        assert "group" not in crumbs[0]
        assert "pks" not in crumbs[0]

    def test_nested_volume_walks_the_full_parent_chain(self) -> None:
        """A volume's breadcrumbs include every ancestor, not just root+self."""
        self._show_full_hierarchy()
        crumbs = self._breadcrumbs(f"/api/v4/browse/volumes/{self.volume.pk}?page=1")
        # root → publisher → imprint → series → volume. Pre-fix this
        # collapsed to [root, volume] because the char-keyed parent-chain
        # map missed the collection-valued group lookup.
        shape = [(c["collection"], c["parentIds"]) for c in crumbs]
        assert shape == [
            ("publishers", []),
            ("publishers", [self.publisher.pk]),
            ("imprints", [self.imprint.pk]),
            ("series", [self.series.pk]),
            ("volumes", [self.volume.pk]),
        ]
        # The redundant legacy group/pks dialect is gone from every crumb.
        assert all("group" not in c and "pks" not in c for c in crumbs)


class HiddenLibraryBreadcrumbsTestCase(TestCase):
    """Crumb names for a library outside the user's groups."""

    @override
    def setUp(self) -> None:
        """One ungrouped library the user can see, one they cannot."""
        cache.clear()
        init_admin_flags()
        self.visible = _seed_library(_VISIBLE_DIR, "Public")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.hidden = _seed_library(_HIDDEN_DIR, _HIDDEN_LABEL)  # pyright: ignore[reportUninitializedInstanceVariable]
        # A library with any group is no longer "ungrouped", and the user
        # belongs to no group, so nothing puts it back in their visible
        # pk set.
        self.hidden["library"].groups.add(
            Group.objects.create(name="breadcrumbs-secret-group")
        )
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="breadcrumbs_outsider", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)
        # Volumes have to be a valid nav collection or the browser
        # redirects on the route shape before it ever names anything.
        response = self.client.patch(
            "/api/v4/browse/publishers/settings",
            data=(
                '{"topCollection": "publishers", "show": {"publishers": true,'
                ' "imprints": true, "series": true, "volumes": true}}'
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_HIDDEN_DIR, ignore_errors=True)
        shutil.rmtree(_VISIBLE_DIR, ignore_errors=True)

    def _assert_no_secret_names(self, url: str) -> None:
        """
        No secret name reaches this user, whatever the response turns out to be.

        Asserted against the whole body rather than the breadcrumb list
        because the fix moves some of these routes off 200: a collection
        that no longer resolves redirects instead (``303`` carrying the
        route in the body, with no ``Location`` header). Pre-fix they
        answered 200 with the hidden names in the trail.
        """
        body = self.client.get(url).content.decode()
        found = {name for name in _SECRET_NAMES if name in body}
        assert not found, (url, found, body)

    def test_volume_crumbs_name_nothing_from_a_hidden_library(self) -> None:
        """The whole FK parent chain is resolved from the route pks."""
        pk = self.hidden["volume"].pk
        self._assert_no_secret_names(f"/api/v4/browse/volumes/{pk}?page=1")

    def test_folder_crumbs_name_nothing_from_a_hidden_library(self) -> None:
        """The ancestor walk resolves names from ``path`` prefixes."""
        pk = self.hidden["folder"].pk
        self._assert_no_secret_names(f"/api/v4/browse/folders/{pk}?page=1")

    def test_metadata_lists_name_nothing_from_a_hidden_library(self) -> None:
        """
        The ``*_list`` chips resolve container names off the raw route pks.

        A mixed selection is what makes this reachable: the visible
        series keeps the metadata object resolving, and the hidden one
        rides along into the parent-container lookup.
        """
        pks = f"{self.visible['series'].pk},{self.hidden['series'].pk}"
        self._assert_no_secret_names(f"/api/v4/browse/series/{pks}/metadata")
