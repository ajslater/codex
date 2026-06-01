"""
Tests for the lazy metadata-import endpoint.

The view dispatches a ``LazyImportComicsTask`` only for browse groups that
resolve to a set of comics (comics / folders). Post the group→collection
flip the dispatch gate read single-char codes against collection-valued
``kwargs["group"]`` and silently never fired — these pin the collection
vocabulary at the enqueue edge.
"""

from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.librarian.scribe.tasks import LazyImportComicsTask

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_QUEUE_PATCH: Final = "codex.views.lazy_import.LIBRARIAN_QUEUE"
_HTTP_OK: Final = 200


class LazyImportViewTestCase(TestCase):
    """Enqueue behavior for /browse/{collection}/{parent_ids}/import."""

    @override
    def setUp(self) -> None:
        """Authenticate a plain user; seed admin flags for the permission check."""
        from django.core.cache import cache

        from codex.startup import init_admin_flags

        cache.clear()
        init_admin_flags()
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="lazyimport", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

    @staticmethod
    def _tasks(mock_queue) -> list:
        return [call.args[0] for call in mock_queue.put.call_args_list]

    @patch(_QUEUE_PATCH)
    def test_comics_group_enqueues_collection_task(self, mock_queue) -> None:
        """A comics-collection import enqueues a task tagged with the collection."""
        response = self.client.post("/api/v4/browse/comics/5,7/import")
        assert response.status_code == _HTTP_OK
        tasks = self._tasks(mock_queue)
        assert any(
            isinstance(t, LazyImportComicsTask)
            and t.group == "comics"
            and t.pks == frozenset({5, 7})
            for t in tasks
        ), tasks

    @patch(_QUEUE_PATCH)
    def test_folders_group_enqueues_collection_task(self, mock_queue) -> None:
        """A folders-collection import also enqueues (folder → its comics)."""
        response = self.client.post("/api/v4/browse/folders/3/import")
        assert response.status_code == _HTTP_OK
        assert any(
            isinstance(t, LazyImportComicsTask) and t.group == "folders"
            for t in self._tasks(mock_queue)
        )

    @patch(_QUEUE_PATCH)
    def test_non_comic_group_does_not_enqueue(self, mock_queue) -> None:
        """A publishers (root) import is not a comic set — nothing enqueued."""
        response = self.client.post("/api/v4/browse/publishers/0/import")
        assert response.status_code == _HTTP_OK
        assert not any(
            isinstance(t, LazyImportComicsTask) for t in self._tasks(mock_queue)
        )
