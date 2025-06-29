"""Extract and Aggregate metadata from comic archive."""

from codex.librarian.scribe.importer.read.extract import (
    ExtractMetadataImporter,
)


class ReadMetadataImporter(ExtractMetadataImporter):
    """Extract and Aggregate metadata from comics to prepare for importing."""

    def read(self):
        """Extract and aggregate metadata."""
        self.extract_metadata()
        self.aggregate_metadata()
