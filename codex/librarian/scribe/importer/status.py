"""Librarian Status for scribe bulk writes."""

from abc import ABC

from codex.librarian.scribe.status import ScribeStatus


class ImporterStatus(ScribeStatus, ABC):
    """Importer Status."""
