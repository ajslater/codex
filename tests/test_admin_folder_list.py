"""The admin folder list the library folder picker browses."""

import shutil
from http import HTTPStatus
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.startup import init_admin_flags
from codex.views.admin.library import AdminFolderListView
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-F042"  # noqa: S105
TMP_DIR = tmp_dir("codex.tests.admin_folder_list")
_URL: Final = "/api/v4/admin/folders"


class AdminFolderListTestCase(TestCase):
    """GET /admin/folders: ordering, parent folder and permission errors."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        for name in ("charlie", "Beta", "alpha", ".hidden"):
            (TMP_DIR / name).mkdir(parents=True, exist_ok=True)
        admin = User.objects.create_user(
            username="admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _get(self, path: str | Path, **params):
        return self.client.get(_URL, {"path": str(path), **params})

    def test_folders_sort_ignoring_case(self) -> None:
        """``Beta`` sorts between ``alpha`` and ``charlie``, not first."""
        response = self._get(TMP_DIR)
        assert response.status_code == HTTPStatus.OK, response.content
        assert response.json()["data"]["folders"] == ["alpha", "Beta", "charlie"]

    def test_hidden_folders_only_on_request(self) -> None:
        response = self._get(TMP_DIR, showHidden="true")
        assert response.status_code == HTTPStatus.OK, response.content
        assert ".hidden" in response.json()["data"]["folders"]

    def test_parent_folder(self) -> None:
        response = self._get(TMP_DIR)
        body = response.json()["data"]
        assert body["rootFolder"] == str(TMP_DIR.resolve())
        assert body["parentFolder"] == str(TMP_DIR.resolve().parent)

    def test_no_parent_folder_at_the_filesystem_root(self) -> None:
        response = self._get("/")
        assert response.status_code == HTTPStatus.OK, response.content
        body = response.json()["data"]
        assert body["parentFolder"] is None

    def test_an_unlistable_folder_is_a_400(self) -> None:
        """Not a logged traceback and a "Server Error"."""
        # The view's own listing, not os.scandir: that is the global os
        # module, and servestatic scans the static root with it too.
        with patch.object(
            AdminFolderListView,
            "_get_dirs",
            side_effect=PermissionError("Operation not permitted"),
        ):
            response = self._get(TMP_DIR)
        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        errors = response.json()["errors"]
        assert errors[0]["detail"] == {"path": ["Permission denied"]}, errors
