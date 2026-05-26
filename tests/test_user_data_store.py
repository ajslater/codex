"""Tests for the user-data sidecar store."""

from __future__ import annotations

from pathlib import Path
from typing import Final, override

import pytest
from django.test import TestCase

from codex.user_data.store import SCHEMA_VERSION, SidecarStore, reset_store_for_tests

_TMP_DIR: Final = Path("/tmp/codex.tests.sidecar")  # noqa: S108
_EXPECTED_BOOKMARK_PAGE: Final = 7


class SidecarStoreTests(TestCase):
    """Behavioral tests for the sidecar SQLite store."""

    @override
    def setUp(self) -> None:
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.sidecar_path = _TMP_DIR / "user_data.sqlite"
        # Pristine file for every test.
        for suffix in ("", "-wal", "-shm"):
            target = self.sidecar_path.with_name(self.sidecar_path.name + suffix)
            target.unlink(missing_ok=True)
        self.store = SidecarStore(self.sidecar_path)  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        self.store.close()
        reset_store_for_tests(None)

    def test_schema_created_on_first_use(self) -> None:
        """Schema is laid down on first connection and stamps the version."""
        conn = self.store.connection()
        version = conn.execute("SELECT version FROM schema_version").fetchone()
        assert version["version"] == SCHEMA_VERSION

    def test_upsert_inserts_then_updates(self) -> None:
        """upsert(...) writes a fresh row, then updates existing columns."""
        self.store.upsert(
            "users",
            ("username",),
            {"username": "alice", "email": "a@x", "is_staff": 0},
        )
        self.store.upsert(
            "users",
            ("username",),
            {"username": "alice", "email": "a@y", "is_staff": 1},
        )
        conn = self.store.connection()
        row = conn.execute(
            "SELECT email, is_staff FROM users WHERE username=?", ("alice",)
        ).fetchone()
        assert row["email"] == "a@y"
        assert row["is_staff"] == 1

    def test_upsert_preserves_unspecified_columns(self) -> None:
        """A partial upsert leaves untouched columns alone."""
        self.store.upsert(
            "users",
            ("username",),
            {"username": "bob", "email": "b@x", "first_name": "Bob"},
        )
        # Second upsert omits ``first_name`` — it must survive.
        self.store.upsert("users", ("username",), {"username": "bob", "email": "b@y"})
        row = (
            self.store.connection()
            .execute("SELECT email, first_name FROM users WHERE username=?", ("bob",))
            .fetchone()
        )
        assert row["email"] == "b@y"
        assert row["first_name"] == "Bob"

    def test_delete_removes_matching_row(self) -> None:
        """delete(...) removes the row, identified by key columns."""
        self.store.upsert("admin_flags", ("key",), {"key": "FOO", "on_flag": 1})
        self.store.delete("admin_flags", {"key": "FOO"})
        rows = self.store.fetchall("admin_flags")
        assert rows == []

    def test_composite_pk_upsert(self) -> None:
        """Composite-PK tables (bookmarks) round-trip correctly."""
        self.store.upsert(
            "bookmarks",
            ("username", "comic_path"),
            {
                "username": "alice",
                "comic_path": "/c/a.cbz",
                "page": 5,
                "finished": 0,
            },
        )
        self.store.upsert(
            "bookmarks",
            ("username", "comic_path"),
            {
                "username": "alice",
                "comic_path": "/c/a.cbz",
                "page": 7,
                "finished": 1,
            },
        )
        rows = self.store.fetchall("bookmarks")
        assert len(rows) == 1
        assert rows[0]["page"] == _EXPECTED_BOOKMARK_PAGE
        assert rows[0]["finished"] == 1

    def test_is_empty_tracks_inserts(self) -> None:
        """``is_empty`` returns True before any data write, False after."""
        assert self.store.is_empty()
        self.store.upsert("users", ("username",), {"username": "alice"})
        assert not self.store.is_empty()

    def test_upsert_empty_data_raises(self) -> None:
        """``upsert`` with no columns is a programming error."""
        with pytest.raises(ValueError, match="no columns"):
            self.store.upsert("users", ("username",), {})

    def test_delete_empty_where_raises(self) -> None:
        """``delete`` without a where-clause would be catastrophic."""
        with pytest.raises(ValueError, match="empty where"):
            self.store.delete("users", {})
