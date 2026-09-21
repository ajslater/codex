"""Admin write hooks enqueue their change broadcasts."""

import json
import tempfile
from http import HTTPStatus
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase

from codex.librarian.fs.poller.tasks import FSPollLibrariesTask
from codex.librarian.notifier.tasks import GROUPS_CHANGED_TASK, LIBRARY_CHANGED_TASK
from codex.models import Library

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_LIBRARY_QUEUE: Final = "codex.views.admin.library.LIBRARIAN_QUEUE"
_GROUP_QUEUE: Final = "codex.views.admin.group.LIBRARIAN_QUEUE"


def _queued(queue) -> tuple:
    """Unwrap the tasks a patched librarian queue received."""
    return tuple(call.args[0] for call in queue.put.call_args_list)


class AdminChangeBroadcastTestCase(TestCase):
    """
    Cover the notify-on-change hooks of the library and group viewsets.

    The hooks used to build their broadcast with
    ``dataclasses.replace(LIBRARY_CHANGED_TASK, mtime=...)`` — a field
    ``NotifierTask`` does not have — and to gate themselves on camelCase
    keys that the JSON:API parser has already un-camelized.
    """

    @override
    def setUp(self) -> None:
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="adminb", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.admin)

    @staticmethod
    def _make_library() -> Library:
        path = tempfile.mkdtemp(prefix="codex.lb.")
        return Library.objects.create(path=path)

    def _patch(self, resource_type, pk, attributes):
        """PATCH one admin resource with a wrapped attributes block."""
        body = {
            "data": {"type": resource_type, "id": str(pk), "attributes": attributes}
        }
        return self.client.patch(
            f"/api/v4/admin/{resource_type}/{pk}",
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_destroy_library_broadcasts(self) -> None:
        """DELETE a library succeeds and announces the change."""
        library = self._make_library()
        with patch(_LIBRARY_QUEUE) as queue:
            resp = self.client.delete(f"/api/v4/admin/libraries/{library.pk}")
        assert resp.status_code == HTTPStatus.NO_CONTENT, resp.content
        assert not Library.objects.filter(pk=library.pk).exists()
        assert LIBRARY_CHANGED_TASK in _queued(queue)

    def test_update_library_groups_broadcasts(self) -> None:
        """Changing a library's groups announces the change."""
        library = self._make_library()
        group = Group.objects.create(name="lib-group")
        with patch(_LIBRARY_QUEUE) as queue:
            resp = self._patch("libraries", library.pk, {"groups": [group.pk]})
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert LIBRARY_CHANGED_TASK in _queued(queue)

    def test_update_library_poll_every_repolls(self) -> None:
        """Changing the poll schedule re-polls the library."""
        library = self._make_library()
        with patch(_LIBRARY_QUEUE) as queue:
            resp = self._patch("libraries", library.pk, {"pollEvery": "02:00:00"})
        assert resp.status_code == HTTPStatus.OK, resp.content
        tasks = _queued(queue)
        assert any(isinstance(task, FSPollLibrariesTask) for task in tasks), tasks

    def test_update_group_membership_broadcasts(self) -> None:
        """Changing a group's libraries and users announces the change."""
        group = Group.objects.create(name="edit-group")
        library = self._make_library()
        with patch(_GROUP_QUEUE) as queue:
            resp = self._patch(
                "groups",
                group.pk,
                {"librarySet": [library.pk], "userSet": [self.admin.pk]},
            )
        assert resp.status_code == HTTPStatus.OK, resp.content
        assert GROUPS_CHANGED_TASK in _queued(queue)

    def test_create_group_broadcasts(self) -> None:
        """Creating a group announces the change even with only a name."""
        body = {"data": {"type": "groups", "attributes": {"name": "new-group"}}}
        with patch(_GROUP_QUEUE) as queue:
            resp = self.client.post(
                "/api/v4/admin/groups",
                data=json.dumps(body),
                content_type="application/json",
            )
        assert resp.status_code == HTTPStatus.CREATED, resp.content
        assert GROUPS_CHANGED_TASK in _queued(queue)

    @override
    def tearDown(self) -> None:
        """Remove the temp library dirs this case created."""
        for path in Path(tempfile.gettempdir()).glob("codex.lb.*"):
            path.rmdir()
