"""Status code to title map."""

from itertools import chain

from bidict import frozenbidict

from codex.librarian.covers.status import COVERS_STATII
from codex.librarian.restarter.status import RESTARTER_STATII
from codex.librarian.scribe.importer.statii.create import CREATE_STATII
from codex.librarian.scribe.importer.statii.delete import REMOVE_STATII
from codex.librarian.scribe.importer.statii.failed import FAILED_IMPORTS_STATII
from codex.librarian.scribe.importer.statii.link import LINK_STATII
from codex.librarian.scribe.importer.statii.query import QUERY_STATII
from codex.librarian.scribe.importer.statii.read import READ_STATII
from codex.librarian.scribe.importer.statii.search import IMPORTER_SEARCH_INDEX_STATII
from codex.librarian.scribe.janitor.status import JANITOR_STATII
from codex.librarian.scribe.search.status import SEARCH_INDEX_STATII
from codex.librarian.scribe.status import SCRIBE_STATII
from codex.librarian.watchdog.status import WATCHDOG_STATII

_STATII = (
    RESTARTER_STATII,
    COVERS_STATII,
    WATCHDOG_STATII,
    JANITOR_STATII,
    SEARCH_INDEX_STATII,
    SCRIBE_STATII,
    CREATE_STATII,
    REMOVE_STATII,
    LINK_STATII,
    QUERY_STATII,
    READ_STATII,
    IMPORTER_SEARCH_INDEX_STATII,
    FAILED_IMPORTS_STATII,
)


ADMIN_STATUS_TITLES = frozenbidict(
    sorted((status.CODE, status.title()) for status in chain.from_iterable(_STATII))
)
