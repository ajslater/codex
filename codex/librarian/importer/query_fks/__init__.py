"""Query missing foreign keys."""

from itertools import chain
from types import MappingProxyType

from codex.librarian.importer.const import (
    COMIC_PATHS,
    FK_CREATE,
    FKC_CREATE_FKS,
    FKC_CREATE_GROUPS,
    FKC_CREDITS,
    FKC_FOLDER_PATHS,
    FKC_IDENTIFIERS,
    FKC_STORY_ARC_NUMBERS,
    FKC_TOTAL_FKS,
    FKC_UPDATE_GROUPS,
    GROUP_MODEL_COUNT_FIELDS,
    QUERY_MODELS,
)
from codex.librarian.importer.query_fks.folders import QueryForeignKeysFoldersImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.status import Status
from codex.models import (
    Credit,
    StoryArcNumber,
)
from codex.models.named import Identifier

_DICT_MODEL_KEY_MAP = MappingProxyType(
    {
        Credit: FKC_CREDITS,
        StoryArcNumber: FKC_STORY_ARC_NUMBERS,
        Identifier: FKC_IDENTIFIERS,
    }
)


class QueryForeignKeysImporter(QueryForeignKeysFoldersImporter):
    """Methods for querying missing fks."""

    def _get_create_fks_totals(self):
        fkc = self.metadata[FK_CREATE]
        total_fks = 0
        for data_group in chain(
            fkc[FKC_CREATE_GROUPS].values(),
            fkc[FKC_UPDATE_GROUPS].values(),
            fkc[FKC_CREATE_FKS].values(),
        ):
            total_fks += len(data_group)
        total_fks += (
            len(fkc[FKC_FOLDER_PATHS])
            + len(fkc[FKC_CREDITS])
            + len(fkc[FKC_STORY_ARC_NUMBERS])
            + len(fkc[FKC_IDENTIFIERS])
        )
        return total_fks

    def query_all_missing_fks(self):
        """Get objects to create by querying existing objects for the proposed fks."""
        if QUERY_MODELS not in self.metadata:
            return
        self.metadata[FK_CREATE] = {
            FKC_CREDITS: set(),
            FKC_STORY_ARC_NUMBERS: set(),
            FKC_IDENTIFIERS: set(),
            FKC_CREATE_GROUPS: {},
            FKC_UPDATE_GROUPS: {},
            FKC_FOLDER_PATHS: set(),
            FKC_CREATE_FKS: {},
        }
        self.log.debug(
            f"Querying existing foreign keys for comics in {self.library.path}"
        )
        status = Status(ImportStatusTypes.QUERY_MISSING_TAGS)
        try:
            self.status_controller.start(status)
            for query_model, create_objs_key in _DICT_MODEL_KEY_MAP.items():
                self.query_missing_dict_model(
                    query_model,
                    create_objs_key,
                    status,
                )
            for group_class in GROUP_MODEL_COUNT_FIELDS:
                if groups := self.metadata[QUERY_MODELS].pop(group_class, None):
                    self.query_missing_group(
                        groups,
                        group_class,
                        status,
                    )

            self.add_missing_folder_paths(
                self.metadata[QUERY_MODELS].pop(COMIC_PATHS, ()), status
            )

            for fk_class in tuple(self.metadata[QUERY_MODELS].keys()):
                self.query_one_simple_model(fk_class, status)
            self.metadata.pop(QUERY_MODELS)
        finally:
            total_fks = self._get_create_fks_totals()
            create_status = Status(ImportStatusTypes.CREATE_TAGS, 0, total_fks)
            self.status_controller.update(create_status, notify=False)
            self.metadata[FK_CREATE][FKC_TOTAL_FKS] = total_fks
            self.status_controller.finish(status)
