"""Every Abort the admin Jobs tab shows is a task the task endpoint runs."""

from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.choices.jobs import ADMIN_JOBS
from codex.views.admin.tasks import _TASK_MAP

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_RUN: Final = "/api/v4/admin/tasks/run"


def _aborts() -> set[str]:
    aborts = set()
    for group in ADMIN_JOBS["ADMIN_JOBS"]:
        if abort := group.get("abort"):
            aborts.add(abort)
        aborts |= {job["abort"] for job in group["jobs"] if job.get("abort")}
    return aborts


class AdminJobAbortTests(TestCase):
    """The Abort buttons post their task to the same endpoint as the jobs."""

    @override
    def setUp(self) -> None:
        User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.login(username="admin", password=_PW)

    def test_every_abort_runs(self) -> None:
        """Each abort is accepted and queues its task."""
        aborts = _aborts()
        assert aborts
        for abort in sorted(aborts):
            assert abort in _TASK_MAP, abort
            with patch("codex.views.admin.tasks.LIBRARIAN_QUEUE") as queue:
                response = self.client.post(
                    _RUN, {"task": abort}, content_type="application/json"
                )
            assert response.status_code == _OK, (abort, response.content)
            queue.put.assert_called_once()
