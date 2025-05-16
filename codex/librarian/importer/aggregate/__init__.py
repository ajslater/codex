"""Aggregate metadata from comcs to prepare for importing."""

from comicbox.schemas.comicbox import (
    COVER_DATE_KEY,
    DATE_KEY,
    NUMBER_KEY,
    STORE_DATE_KEY,
    STORIES_KEY,
    SUFFIX_KEY,
)

from codex.librarian.importer.aggregate.many_to_many import (
    AggregateManyToManyMetadataImporter,
)
from codex.librarian.importer.const import (
    COMIC_PATHS,
    COMIC_VALUES,
    EXTRACTED,
    FIS,
    FK_LINK,
    M2M_LINK,
    QUERY_MODELS,
    SKIPPED,
)
from codex.librarian.importer.status import ImportStatusTypes
from codex.status import Status

_UNUSED_COMICBOX_FIELDS = (
    "alternate_images",
    "bookmark",
    "credit_primaries",
    "ext",
    "manga",
    "pages",
    "prices",  # add
    "protagonist",  # add
    "remainders",
    "reprints",  # add
    "universes",  # add
    "updated_at",
)


class AggregateMetadataImporter(AggregateManyToManyMetadataImporter):
    """Aggregate metadata from comics to prepare for importing."""

    @staticmethod
    def _transform_metadata(md):
        for key in _UNUSED_COMICBOX_FIELDS:
            md.pop(key, None)

        if date := md.pop(DATE_KEY, None):
            date.pop(COVER_DATE_KEY, None)
            date.pop(STORE_DATE_KEY, None)
            md.update(date)

        if issue := md.pop("issue", None):
            if number := issue.pop(NUMBER_KEY, None):
                md["issue_number"] = number
            if suffix := issue.pop(SUFFIX_KEY, None):
                md["issue_suffix"] = suffix

        if stories := md.pop(STORIES_KEY, None):
            md["name"] = "; ".join(stories)

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

    def aggregate_metadata(
        self,
        status=None,
    ):
        """Get aggregated metadata for the paths given."""
        num_extracted_paths = len(self.metadata[EXTRACTED])
        self.log.info(
            f"Aggregating tags from {num_extracted_paths} comics in {self.library.path}..."
        )
        status = Status(ImportStatusTypes.AGGREGATE_TAGS, 0, num_extracted_paths)
        self.status_controller.start(status, notify=False)

        # Init metadata, extract and aggregate
        self.metadata[COMIC_VALUES] = {}
        self.metadata[M2M_LINK] = {}
        self.metadata[QUERY_MODELS] = {COMIC_PATHS: set()}
        self.metadata[FK_LINK] = {}
        self.metadata[FIS] = {}
        # Aggregate further

        for path in self.metadata[EXTRACTED]:
            md = self.metadata[EXTRACTED].pop(path)
            self._transform_metadata(md)
            self._aggregate_path(md, path, status)
        del self.metadata[EXTRACTED]

        fis = self.metadata[FIS].keys()
        skip_paths = frozenset(fis | self.metadata[SKIPPED])
        self.task.files_modified -= skip_paths
        self.task.files_created -= skip_paths
        del self.metadata[SKIPPED]

        # Set statii
        fi_status = Status(ImportStatusTypes.FAILED_IMPORTS, 0, len(fis))
        self.status_controller.update(
            fi_status,
            notify=False,
        )
        count = status.complete if status else 0
        self.log.success(f"Aggregated tags from {count} comics.")

        self.status_controller.finish(status)
        return count
