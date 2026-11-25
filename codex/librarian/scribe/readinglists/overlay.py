"""
A reading list's hand edits: what a recompute keeps.

Hand edits are saved in Codex only: a comic picked by hand, an entry marked
missing, a hidden entry, and a best guess a person let stand. A recompute
builds the list afresh from its sources, so each edit has to find its entry
again by the entry's identity.

An entry is known by every key comicbox gives it (``entry_keys``: each issue
id, best ranked database first, then the name keys), and a combined entry
gains keys as sources join it: a Metron source puts Metron's id first on a
list keyed by Comic Vine. So an edit finds its entry by any key the two
share, unless their volumes differ (``Discriminators.conflicts``): X-Folk
(1963) and X-Folk (1991) may both be volume 1 and share that name key. Each
edit is used once, in list order, so the two entries of an issue a list
reads twice keep their own edits.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from comicbox.readinglists import Discriminators, discriminators, entry_keys

from codex.librarian.scribe.readinglists.references import typed_reference
from codex.models.readinglist import ReadingListEntry, ReadingListMatchTier

EntryKey = tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class Identity:
    """Every key an entry is known by, and what tells its volume."""

    keys: frozenset[EntryKey]
    volume: Discriminators


def reference_identity(reference: Mapping[str, Any]) -> Identity:
    """Return the keys and volume an entry's reference is known by."""
    typed = typed_reference(reference)
    return Identity(frozenset(entry_keys(typed)), discriminators(typed))


@dataclass(slots=True)
class Edit:
    """
    What a person did to one entry.

    ``picked_pk`` is a comic chosen by hand; ``marked_missing`` says the
    library does not have the issue. ``accepted_pk`` is the comic the entry
    held with no review flag, so a recompute that finds that comic again
    leaves the flag cleared.
    """

    keys: frozenset[EntryKey]
    volume: Discriminators = field(default_factory=Discriminators)
    picked_pk: int | None = None
    marked_missing: bool = False
    ignored: bool = False
    accepted_pk: int | None = None

    @classmethod
    def of(cls, entry: ReadingListEntry, identity: Identity) -> "Edit":
        """Read the edits off a current entry."""
        comic_pk: int | None = entry.comic_id  # pyright: ignore[reportAttributeAccessIssue]
        picked = entry.match_tier == ReadingListMatchTier.MANUAL.value
        return cls(
            keys=identity.keys,
            volume=identity.volume,
            picked_pk=comic_pk if picked else None,
            marked_missing=entry.match_tier
            == ReadingListMatchTier.MARKED_MISSING.value,
            ignored=entry.ignored,
            accepted_pk=None if picked or entry.needs_review else comic_pk,
        )

    @property
    def decided(self) -> bool:
        """Whether a person said which comic this is, or that there is none."""
        return self.picked_pk is not None or self.marked_missing

    def absorb(self, other: "Edit") -> None:
        """Take another list's edits of the same issue where this has none."""
        self.keys |= other.keys
        if not self.decided:
            self.picked_pk = other.picked_pk
            self.marked_missing = other.marked_missing
        self.ignored = self.ignored or other.ignored
        if self.accepted_pk is None:
            self.accepted_pk = other.accepted_pk


@dataclass(slots=True)
class Overlay:
    """A list's edits in list order, and its hand-added entries."""

    edits: list[Edit] = field(default_factory=list)
    # A hand-added entry and the index of the edit before it, if any.
    manual: list[tuple[int | None, ReadingListEntry]] = field(default_factory=list)

    @classmethod
    def of(cls, entries: Iterable[ReadingListEntry]) -> "Overlay":
        """Read the hand edits off a list's current entries, in list order."""
        overlay = cls()
        previous: int | None = None
        for entry in entries:
            if entry.manual:
                overlay.manual.append((previous, entry))
                continue
            # An entry with no key cannot be found again.
            identity = reference_identity(entry.reference)
            if identity.keys:
                overlay.edits.append(Edit.of(entry, identity))
                previous = len(overlay.edits) - 1
        return overlay

    def picked_pks(self) -> set[int]:
        """Return the comics people picked by hand."""
        return {edit.picked_pk for edit in self.edits if edit.picked_pk is not None}

    def assign(self, rows: Sequence[Identity]) -> list[int | None]:
        """
        Give each row, in order, the first unused edit sharing a key with it.

        An edit of another volume is never a row's, though they share a key.
        Returns the edit index per row, or None.
        """
        by_key: defaultdict[EntryKey, list[int]] = defaultdict(list)
        for index, edit in enumerate(self.edits):
            for key in edit.keys:
                by_key[key].append(index)
        used: set[int] = set()
        assigned: list[int | None] = []
        for row in rows:
            candidates = (
                index
                for key in row.keys
                for index in by_key.get(key, ())
                if index not in used
                and not self.edits[index].volume.conflicts(row.volume)
            )
            if (best := min(candidates, default=None)) is not None:
                used.add(best)
            assigned.append(best)
        return assigned

    def absorb(self, other: "Overlay") -> None:
        """
        Take in the edits of a list combined into this one.

        An edit of an issue this list has merges into this list's edit,
        whose own edits win; any other edit is added. The other list's
        hand-added entries keep their places after the entries they
        followed.
        """
        assigned = self.assign(
            [Identity(edit.keys, edit.volume) for edit in other.edits]
        )
        moved: dict[int, int] = {}
        for other_index, (edit, mine) in enumerate(
            zip(other.edits, assigned, strict=True)
        ):
            if mine is None:
                self.edits.append(edit)
                moved[other_index] = len(self.edits) - 1
            else:
                self.edits[mine].absorb(edit)
                moved[other_index] = mine
        self.manual.extend(
            (None if previous is None else moved.get(previous), entry)
            for previous, entry in other.manual
        )
