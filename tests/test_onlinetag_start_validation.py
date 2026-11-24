"""
A scan the daemon cannot run is refused before the 202, not lost after it.

The start endpoint answered 202 for any effort string and, by default, for
all three sources whether or not each had a key. The daemon then raised
``ValueError`` (effort) or ``OnlineConfigurationError`` (credentials) and
the admin was left with a spinner. Now an omitted source list means the
sources with keys, in the admin's default order, and a named source
without a key, or an effort comicbox does not know, is a 400. A Resume
whose stored sources have since lost their key is refused the same way.
"""

import json
from http import HTTPStatus
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import Client, TestCase

from codex.librarian.onlinetag.session_snapshot import set_resume_state
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.models import ComicboxTaggingDefaults
from tests.onlinetag_session_fakes import TMP_DIR, make_comic

_PW: Final = "test-pw-hush-S106"
_START_URL: Final = "/api/v4/admin/tag-sessions/start"
_RESUME_URL: Final = "/api/v4/admin/tag-sessions/resume"
_QUEUE_TARGET: Final = "codex.views.admin.onlinetag.LIBRARIAN_QUEUE"


class StartValidationTests(TestCase):
    """Only Metron has a key."""

    @override
    def setUp(self) -> None:
        caches["tagging"].clear()
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "t", "default_sources": []}
        )
        self.comic = make_comic()  # pyright: ignore[reportUninitializedInstanceVariable]
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(admin)

    @override
    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _start(self, **body):
        payload = {"collection": "comics", "pks": [str(self.comic.pk)], **body}
        with patch(_QUEUE_TARGET) as queue:
            response = self.client.post(
                _START_URL, data=json.dumps(payload), content_type="application/json"
            )
        tasks = [call.args[0] for call in queue.put.call_args_list]
        return response, tasks

    def test_no_sources_means_the_keyed_ones(self) -> None:
        """An omitted source list runs only the sources with keys."""
        response, (task,) = self._start()
        assert response.status_code == HTTPStatus.ACCEPTED, response.content
        assert isinstance(task, BulkOnlineTagTask)
        assert task.sources == ("metron",)

    def test_an_empty_source_list_is_refused(self) -> None:
        """Naming no source at all is a 400, not every keyed source."""
        response, tasks = self._start(sources=[])
        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert "Choose at least one source." in response.content.decode()
        assert tasks == []

    def test_an_unkeyed_source_is_refused(self) -> None:
        """Naming a source with no key is a 400, and nothing is queued."""
        response, tasks = self._start(sources=["metron", "comicvine"])
        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert "comicvine" in response.content.decode()
        assert tasks == []

    def test_an_unknown_effort_is_refused(self) -> None:
        """An effort comicbox does not know is a 400, and nothing is queued."""
        response, tasks = self._start(sources=["metron"], effort="nonsense")
        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert tasks == []

    def test_a_resume_with_a_lost_key_is_refused(self) -> None:
        """A paused scan whose source has since lost its key cannot resume."""
        set_resume_state(
            {"sources": ["metron", "comicvine"], "mode": "auto", "ids": {}},
            [self.comic.pk],
        )
        with patch(_QUEUE_TARGET) as queue:
            response = self.client.post(_RESUME_URL)
        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert "comicvine" in response.content.decode()
        queue.put.assert_not_called()
