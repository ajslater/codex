"""Aggregate metadata from comics to prepare for importing."""

from comicbox.schemas.comicbox import (
    COVER_DATE_KEY,
    DATE_KEY,
    NUMBER_KEY,
    STORE_DATE_KEY,
    SUFFIX_KEY,
    TITLE_KEY,
)

from codex.librarian.scribe.importer.const import (
    CREATE_COMICS,
    EXTRACTED,
    FIS,
    LINK_FKS,
    LINK_M2MS,
    QUERY_MODELS,
)
from codex.librarian.scribe.importer.read.folders import AggregatePathMetadataImporter
from codex.librarian.scribe.importer.statii.failed import (
    ImporterFailedImportsQueryStatus,
)
from codex.librarian.scribe.importer.statii.read import ImporterAggregateStatus

_UNUSED_COMICBOX_FIELDS = (
    "alternate_images",
    "bookmark",
    "credit_primaries",
    "ext",
    "manga",
    "pages",
    "prices",
    "remainders",
    "reprints",
    "updated_at",
)


class AggregateMetadataImporter(AggregatePathMetadataImporter):
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

        if title := md.pop(TITLE_KEY, None):
            md["name"] = title

    def _aggregate_path(self, path, status):
        """Aggregate metadata for one path."""
        # Prepare
        md = self.metadata[EXTRACTED].pop(path)
        self._transform_metadata(md)

        # Aggregate
        self.metadata[LINK_FKS][path] = {}
        self.get_fk_metadata(md, path)
        self.get_m2m_metadata(md, path)
        if md:
            self.get_path_metadata(md, path)
        self.metadata[CREATE_COMICS][str(path)] = md

        # Status
        status.increment_complete()
        self.status_controller.update(status)

    def aggregate_metadata(
        self,
    ):
        """Get aggregated metadata for the paths given."""
        num_extracted_paths = len(self.metadata[EXTRACTED])
        self.log.debug(
            f"Aggregating tags from {num_extracted_paths} comics in {self.library.path}..."
        )
        status = ImporterAggregateStatus(0, num_extracted_paths)
        self.status_controller.start(status)

        # Init metadata, extract and aggregate
        self.metadata[QUERY_MODELS] = {}
        self.metadata[CREATE_COMICS] = {}
        self.metadata[LINK_FKS] = {}
        self.metadata[LINK_M2MS] = {}
        # Aggregate further

        for path in tuple(self.metadata[EXTRACTED]):
            if self.abort_event.is_set():
                return status.complete
            self._aggregate_path(path, status)
        del self.metadata[EXTRACTED]

        fis = self.metadata[FIS].keys()

        # Set statii
        fi_status = ImporterFailedImportsQueryStatus(0, len(fis))
        self.status_controller.update(fi_status, notify=False)
        self.status_controller.finish(status)
        return status.complete
