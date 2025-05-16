"""Aggregate metadata from comcs to prepare for importing."""

from codex.choices.admin import AdminFlagChoices
from codex.librarian.importer.aggregate.many_to_many import (
    AggregateManyToManyMetadataImporter,
)
from codex.librarian.importer.const import (
    COMIC_PATHS,
    COMIC_VALUES,
    FIS,
    FK_LINK,
    M2M_LINK,
    QUERY_MODELS,
)
from codex.librarian.importer.status import ImportStatusTypes
from codex.models.admin import AdminFlag
from codex.status import Status


class AggregateMetadataImporter(AggregateManyToManyMetadataImporter):
    """Aggregate metadata from comics to prepare for importing."""

    def _aggregate_path(self, md, path, status):
        """Aggregate metadata for one path."""
        self.metadata[FK_LINK][path] = {}
        self.get_group_tree(md, path)
        self.get_fk_metadata(md, path)
        self.get_m2m_metadata(md, path)
        if md:
            self.metadata[COMIC_VALUES][str(path)] = md
        self.metadata[QUERY_MODELS][COMIC_PATHS].add(path)
        if status:
            status.complete += 1
            self.status_controller.update(status)

    def _set_import_metadata_flag(self):
        """Set import_metadata flag."""
        if self.task.force_import_metadata:
            import_metadata = True
        else:
            key = AdminFlagChoices.IMPORT_METADATA.value
            import_metadata = AdminFlag.objects.get(key=key).on
        if not import_metadata:
            self.log.warning("Admin flag set to NOT import metadata.")
        return import_metadata

    def get_aggregate_metadata(
        self,
        status=None,
    ):
        """Get aggregated metadata for the paths given."""
        all_paths = self.task.files_modified | self.task.files_created
        total_paths = len(all_paths)
        if not total_paths:
            return 0

        self.log.info(
            f"Reading tags from {total_paths} comics in {self.library.path}..."
        )
        status = Status(ImportStatusTypes.AGGREGATE_TAGS, 0, total_paths)
        self.status_controller.start(status, notify=False)

        # Set import_metadata flag
        import_metadata = self._set_import_metadata_flag()

        # Init metadata, extract and aggregate
        self.metadata[COMIC_VALUES] = {}
        self.metadata[M2M_LINK] = {}
        self.metadata[QUERY_MODELS] = {COMIC_PATHS: set()}
        self.metadata[FK_LINK] = {}
        self.metadata[FIS] = {}
        skip_paths = set()
        for path in all_paths:
            if md := self.extract(path, import_metadata=import_metadata):
                self._aggregate_path(md, path, status)
            else:
                skip_paths.add(path)
        num_skip_paths = len(skip_paths)

        # Aggregate further
        fis = self.metadata[FIS].keys()
        skip_paths = frozenset(fis | skip_paths)
        self.task.files_modified -= skip_paths
        self.task.files_created -= skip_paths

        if num_skip_paths:
            self.log.info(
                f"Skipped {num_skip_paths} comics because metadata appears unchanged."
            )

        # Set statii
        fi_status = Status(ImportStatusTypes.FAILED_IMPORTS, 0, len(fis))
        self.status_controller.update(
            fi_status,
            notify=False,
        )
        count = status.complete if status else 0
        self.log.info(f"Aggregated tags from {count} comics.")

        self.status_controller.finish(status)
        return count
