"""
Migration 0061's shelves step keeps its own copies of two live rules.

A migration must not change when application code does, so the step that
turns shelves into lists carries frozen copies of the sort-name rule and the
collection-item identity. These tests prove the copies equal today's live
code. A copy that later falls behind is harmless: the live sync refreshes an
item's identity while it is bound.
"""

import shutil
from importlib import import_module
from typing import Final, override
from uuid import uuid4

from django.test import TestCase

from codex.models import (
    Folder,
    Imprint,
    Library,
    Publisher,
    ReadingList,
    Series,
    Volume,
)
from codex.models import util as model_util
from codex.models.util import get_sort_name
from codex.user_data.identifiers import (
    encode_identifier,
    identifier_for_browse_collection,
)
from tests.tmp_dirs import tmp_dir

_STEP: Final = import_module("codex.migrations._0061_shelves_to_lists")
_TMP_DIR: Final = tmp_dir("codex.tests.migration.frozen")


class FrozenIdentityTests(TestCase):
    """Each item collection's identity is what ``encode_identifier`` makes."""

    @override
    def setUp(self) -> None:
        folder_path = _TMP_DIR / "Ünïcode" / "dd"
        folder_path.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="Marvel")
        imprint = Imprint.objects.create(name="Max", publisher=publisher)
        series = Series.objects.create(
            name='Daredevil "Born Again"', publisher=publisher, imprint=imprint
        )
        self.targets = {  # pyright: ignore[reportUninitializedInstanceVariable]
            "publishers": [publisher],
            "imprints": [imprint],
            "series": [series],
            "volumes": [
                Volume.objects.create(
                    name=1986, series=series, publisher=publisher, imprint=imprint
                ),
                Volume.objects.create(
                    name=1,
                    number_to=3,
                    series=series,
                    publisher=publisher,
                    imprint=imprint,
                ),
                Volume.objects.create(
                    name=None, series=series, publisher=publisher, imprint=imprint
                ),
            ],
            "folders": [
                Folder.objects.create(library=library, path=str(folder_path), name="dd")
            ],
            "arcs": [
                ReadingList.objects.create(name="Civil War", uuid=uuid4()),
            ],
        }

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_every_item_collection_is_covered(self) -> None:
        """The six collections a list holds whole, and no other."""
        assert set(self.targets) == set(_STEP._ITEM_MODELS)  # noqa: SLF001

    def test_identity_equals_the_live_encoding(self) -> None:
        """``ref`` and ``document["identity"]`` match the live identity."""
        for collection, targets in self.targets.items():
            for target in targets:
                live = encode_identifier(
                    collection, identifier_for_browse_collection(collection, target)
                )
                ref, document = _STEP._item_identity(collection, target)  # noqa: SLF001
                assert document["identity"] == live, collection
                assert ref == live[:1024], collection


class FrozenSortNameTests(TestCase):
    """The step's sort names are what ``get_sort_name`` makes."""

    def test_the_article_sets_are_equal(self) -> None:
        """Every language's leading articles, both ways."""
        frozen = _STEP._ARTICLES  # noqa: SLF001
        assert frozen == model_util._ARTICLES  # noqa: SLF001

    def test_sort_names_are_equal(self) -> None:
        """Articles move to the end; a lone word or a non-article stays."""
        names = [
            "The Pile",
            "the",
            "A Long Name Here",
            "L' Avventura",
            "Want to Read",
            "  Los   Muertos ",
            "Der Untergang",
            "ÉL Dorado",
        ] + [f"{article} Thing" for article in sorted(model_util._ARTICLES)]  # noqa: SLF001
        for name in names:
            assert _STEP._sort_name(name) == get_sort_name(name), name  # noqa: SLF001
