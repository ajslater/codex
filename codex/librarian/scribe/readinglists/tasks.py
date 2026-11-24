"""Reading list scribe tasks: write what the fetcher or the admin delivered."""

from dataclasses import dataclass, field
from typing import Any

from codex.librarian.scribe.tasks import ScribeTask


@dataclass(frozen=True)
class ImportItem:
    """
    One list document to store, and where.

    ``source_pk`` refreshes that source. Otherwise the document becomes a
    new source of list ``into_pk``, or of a new list named ``name`` (the
    document's own name when blank), owned by ``user_pk`` or global.
    """

    document: dict[str, Any] | None
    kind: str
    ref: str
    into_pk: int | None = None
    user_pk: int | None = None
    name: str = ""
    source_pk: int | None = None


@dataclass
class ReadingListImportTask(ScribeTask):
    """Store fetched or uploaded reading lists."""

    items: tuple[ImportItem, ...] = ()


@dataclass
class ReadingListRecombineTask(ScribeTask):
    """Recompute lists from their sources, keeping hand edits."""

    list_pks: tuple[int, ...] = ()


@dataclass
class ReadingListRematchTask(ScribeTask):
    """
    Match missing entries again. No pks means every list with any.

    ``seq`` is the scribe queue's sequence number, stamped as the task is
    queued. It lets a full rematch that ran since stand in for this one:
    imports outrank rematches, so a burst of them queues several. A task
    run without the queue, as the nightly janitor runs one, has none.
    """

    list_pks: tuple[int, ...] = field(default_factory=tuple)
    seq: int | None = None


@dataclass
class ReadingListLiveSyncTask(ScribeTask):
    """
    Sync the comics of lists' collection items.

    No pks means every list with an item. Without ``force`` a list syncs
    only when an item's comics changed.
    """

    list_pks: tuple[int, ...] = field(default_factory=tuple)
    force: bool = False
