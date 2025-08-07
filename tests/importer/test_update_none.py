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
    FTS_CREATED_M2MS,
    FTS_EXISTING_M2MS,
    FTS_UPDATE,
    FTS_UPDATED_M2MS,
    LINK_FKS,
    LINK_M2MS,
    TOTAL,
    UPDATE_COMICS,
    UPDATE_FKS,
)
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.models import Comic, Identifier
from tests.importer.test_basic import (
    AGGREGATED,
    COMIC_VALUES_BASIC,
    FILES_DIR,
    FTS_FINAL_BASIC,
    PATH,
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
        UPDATE_COMICS: {1: {}},
        FIS: {},
        CREATE_FKS: {TOTAL: 0},
        UPDATE_FKS: {TOTAL: 0},
        LINK_FKS: {},
        LINK_M2MS: {},
        DELETE_M2MS: {},
        FTS_EXISTING_M2MS: {},
    }
)
CREATED_FK_UPDATE_NONE = MappingProxyType(
    {
        CREATE_COMICS: {},
        DELETE_M2MS: {},
        FIS: {},
        FTS_CREATED_M2MS: {},
        FTS_EXISTING_M2MS: {},
        FTS_UPDATED_M2MS: {},
        LINK_FKS: {},
        LINK_M2MS: {},
        UPDATE_COMICS: {1: {}},
    }
)
CREATED_COMICS_UPDATE_NONE = MappingProxyType(
    {
        DELETE_M2MS: {},
        FIS: {},
        FTS_CREATED_M2MS: {},
        FTS_EXISTING_M2MS: {},
        FTS_UPDATE: {1: {}},
        FTS_UPDATED_M2MS: {},
        LINK_M2MS: {},
    }
)
LINKED_COMICS_UPDATE_NONE = MappingProxyType(
    {
        FIS: {},
        FTS_CREATED_M2MS: {},
        FTS_EXISTING_M2MS: {},
        FTS_UPDATE: {1: {}},
        FTS_UPDATED_M2MS: {},
    }
)
FAILED_IMPORTS_UPDATE_NONE = MappingProxyType(
    {
        FTS_CREATED_M2MS: {},
        FTS_EXISTING_M2MS: {},
        FTS_UPDATE: {1: {}},
        FTS_UPDATED_M2MS: {},
    }
)
DELETED_COMICS_UPDATE_NONE = MappingProxyType(
    {
        FTS_CREATED_M2MS: {},
        FTS_EXISTING_M2MS: {},
        FTS_UPDATE: {1: {}},
        FTS_UPDATED_M2MS: {},
    }
)
FTSED_UPDATE_NONE = MappingProxyType({})


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
        # Query
        self.importer.metadata = deepcopy(dict(AGGREGATED))
        self.importer.query()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(QUERIED_NONE, md, "QUERIED_NONE")

        # Create & Update Fks
        self.importer.create_all_fks()
        self.importer.update_all_fks()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(CREATED_FK_UPDATE_NONE, md, "CREATED_FK_UPDATE_NONE")
        assert Identifier.objects.count() == 3  # noqa: PLR2004

        # Create & Update Comics
        self.importer.update_comics()
        self.importer.create_comics()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(CREATED_COMICS_UPDATE_NONE, md, "CREATED_COMICS_UPDATE_NONE")
        comic = Comic.objects.get(path=PATH)
        assert comic

        # Link
        self.importer.link_comic_m2m_fields()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(LINKED_COMICS_UPDATE_NONE, md, "LINKED_COMICS_UPDATE_NONE")

        comic = test_comic_creation(COMIC_VALUES_BASIC)

        # Fail imports
        self.importer.fail_imports()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(FAILED_IMPORTS_UPDATE_NONE, md, "FAILED_IMPORTS_UPDATE_NONE")

        # Delete
        self.importer.delete()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(DELETED_COMICS_UPDATE_NONE, md, "DELETED_COMICS_UPDATE_NONE")

        # FTS
        self.importer.full_text_search()
        md = MappingProxyType(self.importer.metadata)
        diff_assert(FTSED_UPDATE_NONE, md, "FTSED_UPDATE_NONE")
        test_fts_creation(FTS_FINAL_BASIC, comic)
