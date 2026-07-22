"""Aggregate metadata from comics to prepare for importing."""

from comicbox.formats.comicbox.schema import (
    ALTERNATIVE_ISSUE_KEY,
    AVERAGE_RATING_KEY,
    COMMUNITY_RATING_KEY,
    COVER_DATE_KEY,
    DATE_KEY,
    NUMBER_KEY,
    RATING_COUNT_KEY,
    STORE_DATE_KEY,
    SUFFIX_KEY,
    TITLE_KEY,
)

from codex.librarian.scribe.importer.const import (
    CREATE_COMICS,
    EXTRACTED,
    EXTRACTED_STAT_ONLY,
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
from codex.settings import USED_COMICBOX_FIELDS


def _flatten_alternative_issue(md) -> None:
    """Flatten alternative_issue parts onto flat columns; keep number 0."""
    if alternative_issue := md.pop(ALTERNATIVE_ISSUE_KEY, None):
        if (number := alternative_issue.pop(NUMBER_KEY, None)) is not None:
            md["alternative_issue_number"] = number
        if suffix := alternative_issue.pop(SUFFIX_KEY, None):
            md["alternative_issue_suffix"] = suffix


def _flatten_community_rating(md) -> None:
    """Flatten community_rating parts onto flat columns; keep average 0."""
    if community_rating := md.pop(COMMUNITY_RATING_KEY, None):
        average = community_rating.pop(AVERAGE_RATING_KEY, None)
        if average is not None:
            md["community_rating"] = average
        if (count := community_rating.pop(RATING_COUNT_KEY, None)) is not None:
            md["community_rating_count"] = count


class AggregateMetadataImporter(AggregatePathMetadataImporter):
    """Aggregate metadata from comics to prepare for importing."""

    @staticmethod
    def _transform_metadata(md) -> None:
        for key in tuple(md.keys()):
            if key not in USED_COMICBOX_FIELDS:
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

        _flatten_alternative_issue(md)
        _flatten_community_rating(md)

        if title := md.pop(TITLE_KEY, None):
            md["name"] = title

    def _aggregate_path(self, path, status) -> None:
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

        # Drain stat-only updates (envelope deltas from comicbox skip
        # results) into CREATE_COMICS without LINK_FKS entries. The
        # query phase will route them to UPDATE_COMICS via the normal
        # diff, and the link phase will leave the existing browser
        # collection FKs untouched (since LINK_FKS lookup misses).
        stat_only = self.metadata.pop(EXTRACTED_STAT_ONLY, {})
        for path, envelope_md in stat_only.items():
            self.metadata[CREATE_COMICS][path] = envelope_md

        fis = self.metadata[FIS].keys()

        # Set statii
        fi_status = ImporterFailedImportsQueryStatus(0, len(fis))
        self.status_controller.update(fi_status, notify=False)
        self.status_controller.finish(status)
        return status.complete
