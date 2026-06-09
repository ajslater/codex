"""
Regression + security-tier tests for the metadata view's ``path`` field.

The metadata dialog renders a "Path" row from ``md.path`` (linking to
``md.parentFolderId``). The backend gates that field through
``_path_security`` in ``copy_intersections.py``, which only preserves the
filesystem path when the current collection is in ``PATH_COLLECTIONS``
(comics + folders), and then relativizes it for non-staff users.

``PATH_COLLECTIONS`` is keyed by the v4 collection *name* vocabulary. When
the group→collection flip changed the ``collection`` kwarg from single
chars (``"c"`` / ``"f"``) to names (``"comics"`` / ``"folders"``), the
``PATH_COLLECTIONS = frozenset({"c", "f"})`` literal was left un-flipped,
so ``"comics" in PATH_COLLECTIONS`` became false and ``_path_security``
blanked ``obj.path = ""`` for *every* comic — the path silently vanished
from the metadata screen.

These tests pin the contract end-to-end through the HTTP layer:

* staff see the full absolute path,
* non-staff with the Folder View flag see the library-relative path
  (the ``library.path`` prefix stripped — server layout stays hidden),
* non-staff without Folder View see no path at all.

so a future char/name desync of ``PATH_COLLECTIONS`` — or a regression in
the per-tier path scrubbing — is caught immediately.
"""

import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.choices.admin import AdminFlagChoices
from codex.models import Comic, Folder, Imprint, Library, Publisher, Series, Volume
from codex.models.admin import AdminFlag
from codex.startup import init_admin_flags

TMP_DIR = Path("/tmp/codex.tests.metadata_path")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class MetadataPathTestCase(TestCase):
    """Pin the ``path`` field on the comic metadata response, per access tier."""

    @override
    def setUp(self) -> None:
        """Seed a single comic with a real on-disk path under one hierarchy."""
        # Migrations don't seed every AdminFlag the request pipeline reads;
        # rely on the same idempotent seeder ``codex.run`` calls at startup.
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )
        comic_path = TMP_DIR / "issue.cbz"
        comic_path.touch()
        self.comic_path = comic_path  # pyright: ignore[reportUninitializedInstanceVariable]
        # What a Folder-View non-staff user should see: the path with the
        # library prefix stripped (``WatchedPath.search_path``).
        self.relative_path = str(comic_path).removeprefix(str(library.path))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library,
            path=comic_path,
            issue_number=1,
            name="issue",
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            size=1,
        )
        # A folder containing that one comic. Its metadata path comes from the
        # comic-intersection (``conflict_path``), which _path_security must now
        # scrub the same way it scrubs a comic's own path.
        folder_path = TMP_DIR / "sub"
        folder_path.mkdir(exist_ok=True)
        self.folder = Folder.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library, path=str(folder_path)
        )
        self.comic.folders.add(self.folder)
        self.client = Client()

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _login(self, *, is_staff: bool, folder_view: bool) -> None:
        """Log in a user at the requested tier and set the Folder View flag."""
        AdminFlag.objects.filter(key=AdminFlagChoices.FOLDER_VIEW.value).update(
            on=folder_view
        )
        user = User.objects.create_user(
            username=f"mp_{is_staff}_{folder_view}",
            password=_TEST_PASSWORD,
            is_staff=is_staff,
        )
        self.client.force_login(user)

    def _get_path(self, collection: str, pk: int) -> str:
        """Return the ``path`` field from a metadata response."""
        url = f"/api/v4/browse/{collection}/{pk}/metadata"
        response = self.client.get(url)
        if response.status_code != _HTTP_OK:
            reason = f"GET {url} returned {response.status_code}: {response.content!r}"
            raise AssertionError(reason)
        return _v4(response).get("path") or ""

    # --- comic (``model is Comic`` — path read straight off the instance) ---

    def test_staff_sees_full_path(self) -> None:
        """Staff get the full absolute path verbatim."""
        # Pre-fix this was blanked to "" because "comics" was tested against
        # the stale {"c", "f"} char set.
        self._login(is_staff=True, folder_view=True)
        assert self._get_path("comics", self.comic.pk) == str(self.comic_path)

    def test_nonstaff_folder_view_sees_relative_path(self) -> None:
        """Non-staff with Folder View get the path with the library prefix removed."""
        self._login(is_staff=False, folder_view=True)
        path = self._get_path("comics", self.comic.pk)
        assert path == self.relative_path, path
        # The server's absolute layout must not leak.
        assert not path.startswith(str(TMP_DIR)), path

    def test_nonstaff_without_folder_view_sees_no_path(self) -> None:
        """Non-staff without Folder View get no path at all."""
        self._login(is_staff=False, folder_view=False)
        assert self._get_path("comics", self.comic.pk) == ""

    # --- folder (``model is Folder`` — path comes from ``conflict_path``,
    # which _copy_conflicting_simple_fields writes *before* _path_security) ---

    def test_folder_staff_sees_full_path(self) -> None:
        """Staff folder view exposes the (intersection) absolute path."""
        self._login(is_staff=True, folder_view=True)
        assert self._get_path("folders", self.folder.pk) == str(self.comic_path)

    def test_folder_nonstaff_folder_view_sees_relative_path(self) -> None:
        """Non-staff folder view scrubs the folder path too (uniform with comics)."""
        self._login(is_staff=False, folder_view=True)
        path = self._get_path("folders", self.folder.pk)
        assert path == self.relative_path, path
        assert not path.startswith(str(TMP_DIR)), path
