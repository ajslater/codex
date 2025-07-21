"""Importer Statii."""

from codex.librarian.scribe.importer.statii.create import CREATE_STATII
from codex.librarian.scribe.importer.statii.delete import REMOVE_STATII
from codex.librarian.scribe.importer.statii.failed import FAILED_IMPORTS_STATII
from codex.librarian.scribe.importer.statii.link import LINK_STATII
from codex.librarian.scribe.importer.statii.moved import MOVED_STATII
from codex.librarian.scribe.importer.statii.query import QUERY_STATII
from codex.librarian.scribe.importer.statii.read import READ_STATII
from codex.librarian.scribe.importer.statii.search import IMPORTER_SEARCH_INDEX_STATII

IMPORTER_STATII = (
    *CREATE_STATII,
    *REMOVE_STATII,
    *LINK_STATII,
    *MOVED_STATII,
    *QUERY_STATII,
    *READ_STATII,
    *IMPORTER_SEARCH_INDEX_STATII,
    *FAILED_IMPORTS_STATII,
)
