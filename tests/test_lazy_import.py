"""
Tests for the lazy metadata-import endpoint.

The view dispatches a ``LazyImportComicsTask`` only for browse groups that
resolve to a set of comics (comics / folders). Post the group→collection
flip the dispatch gate read single-char codes against collection-valued
``kwargs["group"]`` and silently never fired — these pin the collection
vocabulary at the enqueue edge.

The pks that reach ``LIBRARIAN_QUEUE`` are the caller's raw URL segment,
and the librarian trusts whatever it is handed, so they are narrowed by
the library-group / age-rating ACL first. These pin that narrowing too:
a pk in a library the caller cannot browse never reaches the queue, and
an enqueue with nothing left to import does not happen at all.
"""

import shutil
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase

from codex.librarian.scribe.tasks import LazyImportComicsTask
from codex.models import Comic, Folder, Imprint, Library, Publisher, Series, Volume
from codex.models.auth import GroupAuth

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_QUEUE_PATCH: Final = "codex.views.lazy_import.LIBRARIAN_QUEUE"
_HTTP_OK: Final = 200
_TMP_DIR: Final = Path("/tmp/codex.tests.lazy_import")  # noqa: S108
_OPEN_DIR: Final = _TMP_DIR / "open"
_PRIVATE_DIR: Final = _TMP_DIR / "private"


class LazyImportViewTestCase(TestCase):
    """Enqueue behavior for /browse/{collection}/{parent_ids}/import."""

    @override
    def setUp(self) -> None:
        """Seed a visible library and an ACL-restricted one; authenticate."""
        from django.core.cache import cache

        from codex.startup import init_admin_flags

        cache.clear()
        init_admin_flags()
        for path in (_OPEN_DIR, _PRIVATE_DIR):
            path.mkdir(exist_ok=True, parents=True)

        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        imprint = Imprint.objects.create(name="Imp", publisher=self.publisher)
        series = Series.objects.create(
            name="Ser", imprint=imprint, publisher=self.publisher
        )
        self.groups = (  # pyright: ignore[reportUninitializedInstanceVariable]
            self.publisher,
            imprint,
            series,
            Volume.objects.create(
                name="2024", series=series, imprint=imprint, publisher=self.publisher
            ),
        )

        # An ungrouped library is visible to everyone.
        open_library = Library.objects.create(path=str(_OPEN_DIR))
        self.folder = self._make_folder(open_library, _OPEN_DIR)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comics = [  # pyright: ignore[reportUninitializedInstanceVariable]
            self._make_comic(open_library, _OPEN_DIR, f"open{n}", self.folder)
            for n in (1, 2)
        ]

        # A library behind a group the test user does not belong to.
        private_library = Library.objects.create(path=str(_PRIVATE_DIR))
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        private_library.groups.add(readers)
        self.private_folder = self._make_folder(private_library, _PRIVATE_DIR)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.private_comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            private_library, _PRIVATE_DIR, "private", self.private_folder
        )

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="lazyimport", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    @staticmethod
    def _make_folder(library, dir_path: Path) -> Folder:
        """Create the library's root Folder row."""
        return Folder.objects.create(
            library=library, path=str(dir_path), name=dir_path.name
        )

    def _make_comic(self, library, dir_path: Path, name: str, folder: Folder) -> Comic:
        """Create a Comic row backed by a touch file, inside ``folder``."""
        path = dir_path / f"{name}.cbz"
        path.touch()
        publisher, imprint, series, volume = self.groups
        comic = Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name=name,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            parent_folder=folder,
            size=42,
        )
        comic.folders.add(folder)
        return comic

    @staticmethod
    def _tasks(mock_queue) -> list:
        return [call.args[0] for call in mock_queue.put.call_args_list]

    @patch(_QUEUE_PATCH)
    def test_comics_group_enqueues_collection_task(self, mock_queue) -> None:
        """A comics-collection import enqueues a task tagged with the collection."""
        pks = [comic.pk for comic in self.comics]
        csv = ",".join(str(pk) for pk in pks)
        response = self.client.post(f"/api/v4/browse/comics/{csv}/import")
        assert response.status_code == _HTTP_OK
        tasks = self._tasks(mock_queue)
        assert any(
            isinstance(t, LazyImportComicsTask)
            and t.collection == "comics"
            and t.pks == frozenset(pks)
            for t in tasks
        ), tasks

    @patch(_QUEUE_PATCH)
    def test_folders_group_enqueues_collection_task(self, mock_queue) -> None:
        """A folders-collection import also enqueues (folder → its comics)."""
        response = self.client.post(f"/api/v4/browse/folders/{self.folder.pk}/import")
        assert response.status_code == _HTTP_OK
        assert any(
            isinstance(t, LazyImportComicsTask)
            and t.collection == "folders"
            and t.pks == frozenset({self.folder.pk})
            for t in self._tasks(mock_queue)
        )

    @patch(_QUEUE_PATCH)
    def test_non_comic_group_does_not_enqueue(self, mock_queue) -> None:
        """A publishers import is not a comic set — nothing enqueued."""
        response = self.client.post(
            f"/api/v4/browse/publishers/{self.publisher.pk}/import"
        )
        assert response.status_code == _HTTP_OK
        assert not any(
            isinstance(t, LazyImportComicsTask) for t in self._tasks(mock_queue)
        )

    @patch(_QUEUE_PATCH)
    def test_unreachable_comic_never_reaches_the_queue(self, mock_queue) -> None:
        """A pk in a library behind a group the caller isn't in is dropped."""
        csv = f"{self.comics[0].pk},{self.private_comic.pk}"
        response = self.client.post(f"/api/v4/browse/comics/{csv}/import")
        assert response.status_code == _HTTP_OK
        tasks = self._tasks(mock_queue)
        assert [t.pks for t in tasks] == [frozenset({self.comics[0].pk})], tasks

    @patch(_QUEUE_PATCH)
    def test_all_unreachable_enqueues_nothing(self, mock_queue) -> None:
        """Nothing left after the ACL means no task at all, not an empty one."""
        response = self.client.post(
            f"/api/v4/browse/comics/{self.private_comic.pk}/import"
        )
        assert response.status_code == _HTTP_OK
        assert not self._tasks(mock_queue)

    @patch(_QUEUE_PATCH)
    def test_unreachable_folder_never_reaches_the_queue(self, mock_queue) -> None:
        """The folders collection is ACL'd on the same seam as comics."""
        response = self.client.post(
            f"/api/v4/browse/folders/{self.private_folder.pk}/import"
        )
        assert response.status_code == _HTTP_OK
        assert not self._tasks(mock_queue)
