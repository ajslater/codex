"""Test extract metadata importer."""

from abc import ABC
from copy import deepcopy
from threading import Event, Lock
from types import MappingProxyType

from loguru import logger
from typing_extensions import override

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.const import (
    CREATE_COMICS,
    CREATE_FKS,
    DELETE_M2MS,
    FIS,
    FTS_EXISTING_M2MS,
    LINK_FKS,
    LINK_M2MS,
    TOTAL,
    UPDATE_COMICS,
    UPDATE_FKS,
)
from codex.librarian.scribe.importer.importer import ComicImporter
from tests.importer.test_basic import (
    AGGREGATED,
    COMIC_VALUES_BASIC,
    FILES_DIR,
    FTS_FINAL_BASIC,
    QUERIED,
    BaseTestImporter,
    diff_assert,
    test_comic_creation,
    test_fts_creation,
)

UPDATE_PATH = FILES_DIR / "comicbox-2-update.cbz"
QUERIED_NONE = MappingProxyType(
    {
        CREATE_COMICS: {},
        UPDATE_COMICS: {},
        FIS: {},
        CREATE_FKS: {TOTAL: 0},
        UPDATE_FKS: {TOTAL: 0},
        LINK_FKS: {},
        LINK_M2MS: {},
        DELETE_M2MS: {},
        FTS_EXISTING_M2MS: {},
    }
)


class BaseTestImporterUpdate(BaseTestImporter, ABC):
    @override
    def setUp(self):
        super().setUp()
        importer = ComicImporter(self.task, logger, LIBRARIAN_QUEUE, Lock(), Event())
        importer.metadata = deepcopy(dict(QUERIED))
        importer.create_and_update()
        importer.link()
        comic = test_comic_creation(COMIC_VALUES_BASIC)
        importer.full_text_search()
        test_fts_creation(FTS_FINAL_BASIC, comic)


class TestImporterUpdateNone(BaseTestImporterUpdate):
    def test_update_none(self):
        self.importer.metadata = deepcopy(dict(AGGREGATED))
        self.importer.query()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(QUERIED_NONE, md, "QUERIED_NONE")
