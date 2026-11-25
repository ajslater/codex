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
share. Each edit is used once, in list order, so the two entries of an issue
a list reads twice keep their own edits.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from comicbox.readinglists import entry_keys

from codex.librarian.scribe.readinglists.references import typed_reference
from codex.models.readinglist import ReadingListEntry, ReadingListMatchTier

EntryKey = tuple[Any, ...]


def reference_keys(reference: Mapping[str, Any]) -> frozenset[EntryKey]:
    """Return every key an entry's reference is known by."""
    return frozenset(entry_keys(typed_reference(reference)))


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
    picked_pk: int | None = None
    marked_missing: bool = False
    ignored: bool = False
    accepted_pk: int | None = None

    @classmethod
    def of(cls, entry: ReadingListEntry, keys: frozenset[EntryKey]) -> "Edit":
        """Read the edits off a current entry."""
        comic_pk: int | None = entry.comic_id  # pyright: ignore[reportAttributeAccessIssue]
        picked = entry.match_tier == ReadingListMatchTier.MANUAL.value
        return cls(
            keys=keys,
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
            if keys := reference_keys(entry.reference):
                overlay.edits.append(Edit.of(entry, keys))
                previous = len(overlay.edits) - 1
        return overlay

    def picked_pks(self) -> set[int]:
        """Return the comics people picked by hand."""
        return {edit.picked_pk for edit in self.edits if edit.picked_pk is not None}

    def assign(self, rows_keys: Sequence[frozenset[EntryKey]]) -> list[int | None]:
        """
        Give each row, in order, the first unused edit sharing a key with it.

        Returns the edit index per row, or None.
        """
        by_key: defaultdict[EntryKey, list[int]] = defaultdict(list)
        for index, edit in enumerate(self.edits):
            for key in edit.keys:
                by_key[key].append(index)
        used: set[int] = set()
        assigned: list[int | None] = []
        for keys in rows_keys:
            candidates = (
                index
                for key in keys
                for index in by_key.get(key, ())
                if index not in used
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
        assigned = self.assign([edit.keys for edit in other.edits])
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
