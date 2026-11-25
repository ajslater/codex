"""Migration 0061 adds the VerseDB API token, and takes it away again."""

from typing import Final, override

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

_BEFORE: Final = [("codex", "0060_post_v2_6_0_schema")]
_AFTER: Final = [("codex", "0061_reading_lists_and_versedb_key")]
_TABLE: Final = "codex_comicboxtaggingdefaults"


def _latest() -> list[tuple[str, str]]:
    """Return the codex migration the rest of the suite expects."""
    return MigrationExecutor(connection).loader.graph.leaf_nodes("codex")


def _migrate(target):
    """Migrate to ``target`` and return the app registry at that state."""
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    return MigrationExecutor(connection).loader.project_state(target).apps


def _columns() -> set[str]:
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, _TABLE)
    return {column.name for column in description}


class VerseDBKeyMigrationTests(TransactionTestCase):
    """The column adds with an empty default and reverses cleanly."""

    @override
    def setUp(self) -> None:
        self.addCleanup(_migrate, _latest())

    def test_the_field_adds_empty_and_reverses(self) -> None:
        old_apps = _migrate(_BEFORE)
        assert "versedb_key" not in _columns()
        old_apps.get_model("codex", "ComicboxTaggingDefaults").objects.update_or_create(
            pk=1, defaults={"metron_key": "m"}
        )

        new_apps = _migrate(_AFTER)
        assert "versedb_key" in _columns()
        model = new_apps.get_model("codex", "ComicboxTaggingDefaults")
        row = model.objects.values("versedb_key", "metron_key").get(pk=1)
        assert row == {"versedb_key": "", "metron_key": "m"}

        _migrate(_BEFORE)
        assert "versedb_key" not in _columns()
