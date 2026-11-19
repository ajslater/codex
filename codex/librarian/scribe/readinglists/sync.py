"""
Keep the reading lists that come from story-arc tags in step with the tags.

Every distinct ``StoryArc.sort_name`` has one ``tags`` source on one global
list, the grouping arc browse always used. A sync reads every arc link once,
digests each arc's (comic, number) pairs, and touches only the lists whose
digest changed:

- A new arc name gets a new list holding that one source, unless a list
  was written into files as that arc: then the source joins that list.
- A list whose only source is its tags and that nobody edited by hand is
  rebuilt from the tags: one entry per comic, by arc number, then date,
  then pk, NULLs first as SQLite sorts them.
- A list with other sources or hand edits is recombined, which keeps them.
- An arc that is gone loses its source. A list left with no source and no
  hand-added entry is deleted.

Lists are never recreated, so shelf items, custom covers and reader
settings that point at one survive.
"""

from dataclasses import dataclass
from typing import Final, override

from django.db import transaction
from django.db.models import Max, Q
from django.utils.timezone import now

from codex.librarian.scribe.readinglists.arcs import (
    ArcMember,
    arc_members,
    digest,
    is_ordered,
    ordered_members,
)
from codex.librarian.scribe.readinglists.references import comic_references
from codex.librarian.scribe.readinglists.write import WRITTEN_ARC_KEY, written_lists
from codex.models.readinglist import (
    ReadingList,
    ReadingListEntry,
    ReadingListMatchTier,
    ReadingListSource,
    ReadingListSourceKind,
)

STORY_LIST_TYPE: Final = "story"
_BATCH: Final = 1000
_HAND_EDITED: Final = (
    Q(manual=True)
    | Q(ignored=True)
    | Q(
        match_tier__in=(
            ReadingListMatchTier.MANUAL,
            ReadingListMatchTier.MARKED_MISSING,
        )
    )
)


@dataclass(frozen=True, slots=True)
class SyncCounts:
    """What a sync changed."""

    created: int = 0
    updated: int = 0
    deleted: int = 0

    @property
    def changed(self) -> int:
        """Lists touched."""
        return self.created + self.updated + self.deleted

    @override
    def __str__(self) -> str:
        """Say what changed, for a log line."""
        return f"{self.created} created, {self.updated} updated, {self.deleted} deleted"


def is_tags_only(reading_list: ReadingList) -> bool:
    """Whether a list holds only its tags: one source and no hand edits."""
    if reading_list.order_locked:
        return False
    sources = ReadingListSource.objects.filter(reading_list=reading_list)
    if sources.exclude(kind=ReadingListSourceKind.TAGS).exists():
        return False
    entries = ReadingListEntry.objects.filter(reading_list=reading_list)
    return not entries.filter(_HAND_EDITED).exists()


def rebuild_from_tags(
    reading_list: ReadingList,
    source: ReadingListSource,
    comics: dict[int, ArcMember],
) -> None:
    """Replace a tags-only list's entries with its arc's comics."""
    members = ordered_members(comics)
    references = comic_references(pk for pk, _ in members)
    ReadingListEntry.objects.filter(reading_list=reading_list).delete()
    ReadingListEntry.objects.bulk_create(
        (
            ReadingListEntry(
                reading_list=reading_list,
                position=position,
                comic_id=pk,
                reference=references.get(pk, {}),
                series_name=member.series,
                issue=member.issue,
                year=member.year,
                match_tier=ReadingListMatchTier.TAGGED,
                source_ids=[source.pk],
            )
            for position, (pk, member) in enumerate(members)
        ),
        batch_size=_BATCH,
    )


class TagListSync:
    """Sync the lists from story-arc tags; see the module docstring."""

    def __init__(self, recombine=None) -> None:
        """
        Take the general path for lists that are not tags only.

        ``recombine(reading_list)`` rebuilds a list from all its sources and
        keeps its hand edits. Without one, those lists keep their entries
        and only their tags source's revision moves on.
        """
        self._recombine = recombine
        self._created = 0
        self._updated = 0
        self._deleted = 0

    def _create(self, sort_name: str, name: str, comics: dict[int, ArcMember]):
        reading_list = ReadingList.objects.create(
            name=name, sort_name=sort_name, list_type=STORY_LIST_TYPE
        )
        source = ReadingListSource.objects.create(
            reading_list=reading_list,
            kind=ReadingListSourceKind.TAGS,
            ref=sort_name,
            revision=digest(comics),
            ordered=is_ordered(comics),
            fetched_at=now(),
        )
        rebuild_from_tags(reading_list, source, comics)
        self._created += 1

    def _attach(
        self, reading_list: ReadingList, sort_name: str, comics: dict[int, ArcMember]
    ) -> None:
        """Give a list written into files its own arc as its tags source."""
        top = ReadingListSource.objects.filter(reading_list=reading_list).aggregate(
            top=Max("rank")
        )["top"]
        ReadingListSource.objects.create(
            reading_list=reading_list,
            kind=ReadingListSourceKind.TAGS,
            ref=sort_name,
            rank=0 if top is None else top + 1,
            revision=digest(comics),
            ordered=is_ordered(comics),
            fetched_at=now(),
        )
        extra = dict(reading_list.extra)
        extra.pop(WRITTEN_ARC_KEY, None)
        reading_list.extra = extra
        if self._recombine:
            self._recombine(reading_list)
        reading_list.save()
        self._updated += 1

    def _update(
        self, source: ReadingListSource, name: str, comics: dict[int, ArcMember]
    ) -> None:
        reading_list = source.reading_list
        source.revision = digest(comics)
        source.ordered = is_ordered(comics)
        source.fetched_at = now()
        source.save(update_fields=("revision", "ordered", "fetched_at", "updated_at"))
        if "name" not in reading_list.edited_fields:
            reading_list.name = name
        if is_tags_only(reading_list):
            rebuild_from_tags(reading_list, source, comics)
        elif self._recombine:
            self._recombine(reading_list)
        # Bumps updated_at, which the browser's mtime reads.
        reading_list.save()
        self._updated += 1

    def _remove(self, source: ReadingListSource) -> None:
        reading_list = source.reading_list
        source.delete()
        others = ReadingListSource.objects.filter(reading_list=reading_list).exists()
        manual = ReadingListEntry.objects.filter(
            reading_list=reading_list, manual=True
        ).exists()
        if not others and not manual:
            reading_list.delete()
            self._deleted += 1
            return
        if self._recombine:
            self._recombine(reading_list)
        reading_list.save()
        self._updated += 1

    def sync(self) -> SyncCounts:
        """Bring every tags source in step with the tags."""
        names, members = arc_members()
        sources = {
            source.ref: source
            for source in ReadingListSource.objects.filter(
                kind=ReadingListSourceKind.TAGS
            ).select_related("reading_list")
        }
        written = written_lists()
        with transaction.atomic():
            for sort_name, comics in members.items():
                name = names.get(sort_name, sort_name)
                source = sources.pop(sort_name, None)
                if source is None and (
                    reading_list := written.pop(sort_name.casefold(), None)
                ):
                    self._attach(reading_list, sort_name, comics)
                elif source is None:
                    self._create(sort_name, name, comics)
                elif source.revision != digest(comics):
                    self._update(source, name, comics)
            for source in sources.values():
                self._remove(source)
        return SyncCounts(self._created, self._updated, self._deleted)


def sync_tag_lists(recombine=None) -> SyncCounts:
    """
    Sync the lists from story-arc tags.

    ``recombine`` defaults to the real one, sharing one matcher across the
    run. It is imported here because it builds on this module.
    """
    if recombine is None:
        from codex.librarian.scribe.readinglists.combine import recombine as _recombine
        from codex.librarian.scribe.readinglists.matcher import ListMatcher

        matcher = ListMatcher()

        def _with_matcher(reading_list) -> None:
            _recombine(reading_list, matcher)

        recombine = _with_matcher
    return TagListSync(recombine).sync()
