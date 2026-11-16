"""
Tests for migration 0063: tokens become keys; the Stats API key is revoked.

``rest_framework.authtoken`` is no longer installed, so the test database
never gets its table: each test that needs one builds it the way DRF did,
at the 0062 state, then migrates forward to 0063 to check what it became.
The backward leg doubles as the test of the reverse data step.
"""

import hashlib
from typing import Final, override

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

_BEFORE: Final = [("codex", "0062_device_keys")]
_AFTER: Final = [("codex", "0063_api_key_scopes")]
_TOKEN_TABLE: Final = "authtoken_token"  # noqa: S105
_CREATE_TOKEN_TABLE: Final = f"""
CREATE TABLE {_TOKEN_TABLE} (
    "key" varchar(40) NOT NULL PRIMARY KEY,
    "created" datetime NOT NULL,
    "user_id" integer NOT NULL UNIQUE
        REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED
)
"""
_INSERT_TOKEN: Final = f"""
INSERT INTO {_TOKEN_TABLE} (key, created, user_id)
VALUES (%s, '2024-01-01 00:00:00', %s)
"""  # noqa: S608
_RECORD_DRF_MIGRATION: Final = """
INSERT INTO django_migrations (app, name, applied)
VALUES ('authtoken', '0001_initial', '2024-01-01 00:00:00')
"""
_TOKEN_A: Final = "a" * 40
_TOKEN_B: Final = "0123456789abcdef0123456789abcdef01234567"  # noqa: S105
_STATS_SECRET: Final = "QmFzZTY0VXVpZEtleQ"  # noqa: S105


def _migrate(target):
    """Migrate to ``target`` and return the app registry at that state."""
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    return MigrationExecutor(connection).loader.project_state(target).apps


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _md5(value: str) -> str:
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


def _table_exists(name: str) -> bool:
    return name in connection.introspection.table_names()


class ApiKeyMigrationTests(TransactionTestCase):
    """Tokens become universal keys; the server Stats key is revoked."""

    @override
    def setUp(self) -> None:
        self.addCleanup(_migrate, _AFTER)
        self.addCleanup(self._drop_token_table)
        self.admin = User.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", is_staff=True, is_superuser=True
        )
        self.reader = User.objects.create(username="reader")  # pyright: ignore[reportUninitializedInstanceVariable]

    @staticmethod
    def _drop_token_table() -> None:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {_TOKEN_TABLE}")
            cursor.execute("DELETE FROM django_migrations WHERE app = 'authtoken'")

    @staticmethod
    def _seed_tokens(tokens: dict[int, str]) -> None:
        """Build DRF's token table and its migration record, with rows."""
        with connection.cursor() as cursor:
            cursor.execute(_CREATE_TOKEN_TABLE)
            for user_id, key in tokens.items():
                cursor.execute(_INSERT_TOKEN, (key, user_id))
            cursor.execute(_RECORD_DRF_MIGRATION)

    @staticmethod
    def _seed_stats_key(old_apps, value: str = _STATS_SECRET) -> None:
        old_apps.get_model("codex", "AdminFlag").objects.create(key="AK", value=value)

    @staticmethod
    def _keys(new_apps) -> dict[tuple[int, str], dict]:
        rows = new_apps.get_model("codex", "UserApiKey").objects.values()
        return {(row["user_id"], row["name"]): row for row in rows}

    @staticmethod
    def _authtoken_migrations() -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM django_migrations WHERE app = 'authtoken'"
            )
            row = cursor.fetchone()
        assert row is not None
        return row[0]

    def test_tokens_become_universal_keys(self) -> None:
        old_apps = _migrate(_BEFORE)
        # A device key already holds the name, so the token's gets a suffix.
        old_apps.get_model("codex", "UserApiKey").objects.create(
            user_id=self.reader.pk,
            name="Universal Token",
            prefix="dddd",
            digest=_sha256("device"),
            kosync_digest=_md5("device"),
        )
        self._seed_tokens({self.reader.pk: _TOKEN_A, self.admin.pk: _TOKEN_B})

        keys = self._keys(_migrate(_AFTER))

        assert keys[self.reader.pk, "Universal Token"]["scope"] == "device"
        reader = keys[self.reader.pk, "Universal Token (2)"]
        assert reader["scope"] == "universal"
        assert reader["digest"] == _sha256(_TOKEN_A)
        assert reader["kosync_digest"] == _md5(_TOKEN_A)
        assert reader["prefix"] == _TOKEN_A[:4]
        admin = keys[self.admin.pk, "Universal Token"]
        assert admin["scope"] == "universal"
        assert admin["digest"] == _sha256(_TOKEN_B)
        assert not _table_exists(_TOKEN_TABLE)
        assert self._authtoken_migrations() == 0

    def test_a_token_whose_user_is_gone_is_skipped(self) -> None:
        """An orphan token row, its user deleted, must not fail the migration."""
        _migrate(_BEFORE)
        orphan_id = max(User.objects.values_list("pk", flat=True)) + 100
        # SQLite enforces the foreign key at commit; only an orphan can be
        # seeded with the checks off, as a database repaired by hand might be.
        with connection.constraint_checks_disabled():
            self._seed_tokens({self.reader.pk: _TOKEN_A, orphan_id: _TOKEN_B})

        keys = self._keys(_migrate(_AFTER))

        assert set(keys) == {(self.reader.pk, "Universal Token")}
        assert keys[self.reader.pk, "Universal Token"]["digest"] == _sha256(_TOKEN_A)
        assert not _table_exists(_TOKEN_TABLE)

    def test_no_token_table(self) -> None:
        """A database that never had DRF's token table migrates cleanly."""
        _migrate(_BEFORE)
        assert not _table_exists(_TOKEN_TABLE)
        assert self._keys(_migrate(_AFTER)) == {}

    @staticmethod
    def _assert_server_key_revoked(new_apps) -> None:
        """No stats key took its place, and the ``AK`` flag row is gone."""
        api_keys = new_apps.get_model("codex", "UserApiKey").objects
        assert not api_keys.filter(scope="stats").exists()
        flags = new_apps.get_model("codex", "AdminFlag").objects
        assert not flags.filter(key="AK").exists()

    def test_the_server_stats_key_is_revoked(self) -> None:
        """An admin exists to own it, and still no key replaces it."""
        self._seed_stats_key(_migrate(_BEFORE))
        self._assert_server_key_revoked(_migrate(_AFTER))

    def test_an_empty_server_key_row_goes_too(self) -> None:
        self._seed_stats_key(_migrate(_BEFORE), value="")
        self._assert_server_key_revoked(_migrate(_AFTER))

    def test_reverse_keeps_only_device_keys(self) -> None:
        old_apps = _migrate(_BEFORE)
        old_apps.get_model("codex", "UserApiKey").objects.create(
            user_id=self.reader.pk,
            name="Kobo",
            prefix="kkkk",
            digest=_sha256("kobo"),
            kosync_digest=_md5("kobo"),
        )
        self._seed_tokens({self.reader.pk: _TOKEN_A})
        assert len(self._keys(_migrate(_AFTER))) == 2  # noqa: PLR2004

        keys = self._keys(_migrate(_BEFORE))

        assert set(keys) == {(self.reader.pk, "Kobo")}
