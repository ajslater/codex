"""0055 folds the Default View (BG) flag into SettingsDefaults.top_collection."""

import importlib
from typing import Final, override

from django.apps import apps as django_apps
from django.test import TestCase

from codex.models import AdminFlag, SettingsDefaults
from codex.startup import init_admin_flags

# Migration filenames start with digits, so importlib is the only way to reach
# the helpers (mirrors tests/test_settings_collection_flip.py).
_MIGRATION = importlib.import_module("codex.migrations.0055_settings_defaults")
_seed = _MIGRATION.seed_settings_defaults
_unseed = _MIGRATION.unseed_settings_defaults
_BG: Final = "BG"
_FV: Final = "FV"


class SettingsDefaultsMigrationTestCase(TestCase):
    """Every row of the BG mapping table, the seed and the reverse."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        SettingsDefaults.objects.all().delete()

    @staticmethod
    def _set_flags(*, bg: tuple[bool, str] | None, fv: bool | None = True) -> None:
        AdminFlag.objects.filter(key__in=(_BG, _FV)).delete()
        if bg is not None:
            on, value = bg
            AdminFlag.objects.create(key=_BG, on=on, value=value)
        if fv is not None:
            AdminFlag.objects.create(key=_FV, on=fv)

    def _migrated_top(self, *, bg: tuple[bool, str] | None, fv: bool | None = True):
        self._set_flags(bg=bg, fv=fv)
        _seed(django_apps, None)
        return SettingsDefaults.objects.get(pk=1).top_collection

    def test_mapping_table(self) -> None:
        cases: tuple[tuple[tuple[bool, str] | None, bool | None, str], ...] = (
            (None, True, "publishers"),
            ((False, "series"), True, "publishers"),
            ((True, "publishers"), True, "publishers"),
            ((True, "series"), True, "series"),
            ((True, "comics"), True, "comics"),
            ((True, "arcs"), True, "arcs"),
            ((True, "folders"), True, "folders"),
            ((True, "folders"), False, "publishers"),
            ((True, "folders"), None, "publishers"),
            ((True, "imprints"), True, "publishers"),
            ((True, "volumes"), True, "publishers"),
            ((True, "p"), True, "publishers"),
        )
        for bg, fv, expected in cases:
            SettingsDefaults.objects.all().delete()
            assert self._migrated_top(bg=bg, fv=fv) == expected, (bg, fv)

    def test_seed_values_and_bg_deletion(self) -> None:
        self._migrated_top(bg=(True, "series"))
        row = SettingsDefaults.objects.get(pk=1)
        assert row.bookmark == ""
        assert row.table_columns == {}
        assert row.view_mode == "cover"
        assert not AdminFlag.objects.filter(key=_BG).exists()
        assert AdminFlag.objects.filter(key=_FV).exists()

    def test_reverse_recreates_bg(self) -> None:
        self._migrated_top(bg=(True, "arcs"))
        _unseed(django_apps, None)
        flag = AdminFlag.objects.get(key=_BG)
        assert flag.on is True
        assert flag.value == "arcs"
        assert not SettingsDefaults.objects.exists()

    def test_reverse_without_a_row_recreates_publishers(self) -> None:
        _unseed(django_apps, None)
        assert AdminFlag.objects.get(key=_BG).value == "publishers"
