"""
The comics tagged with each story arc, as the reading lists from tags see them.

Shared by the tag sync and the documents a recombine builds, so neither
imports the other.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from hashlib import sha1
from json import dumps

from codex.librarian.scribe.readinglists.references import issue_name
from codex.models import Comic, StoryArc


@dataclass(slots=True)
class ArcMember:
    """A comic tagged with an arc: what orders it and what labels it."""

    number: int | None
    comic_date: date | None
    series: str
    issue: str
    year: int | None


def _lower(number: int | None, known: int | None) -> bool:
    """Whether ``number`` beats ``known``: MIN() ignores NULLs, as arc browse did."""
    return number is not None and (known is None or number < known)


def arc_members() -> tuple[dict[str, str], dict[str, dict[int, ArcMember]]]:
    """
    Read every arc link once.

    Returns each sort name's first spelling, and its comics with each
    comic's lowest number in that arc.
    """
    names: dict[str, str] = {}
    for name, sort_name in StoryArc.objects.order_by("pk").values_list(
        "name", "sort_name"
    ):
        names.setdefault(sort_name, name)
    through = Comic.story_arc_numbers.through
    rows = through.objects.values_list(
        "storyarcnumber__story_arc__sort_name",
        "comic_id",
        "storyarcnumber__number",
        "comic__date",
        "comic__series__name",
        "comic__issue_number",
        "comic__issue_suffix",
        "comic__year",
    )
    members: dict[str, dict[int, ArcMember]] = defaultdict(dict)
    for sort_name, comic_pk, number, comic_date, series, issue, suffix, year in rows:
        comics = members[sort_name]
        known = comics.get(comic_pk)
        if known is not None and not _lower(number, known.number):
            continue
        comics[comic_pk] = ArcMember(
            number=number,
            comic_date=comic_date,
            series=series or "",
            issue=issue_name(issue, suffix),
            year=year,
        )
    return names, members


def _sort_key(item: tuple[int, ArcMember]) -> tuple:
    """Arc number, then date, then pk, NULLs first."""
    pk, member = item
    return (
        member.number is not None,
        member.number or 0,
        member.comic_date is not None,
        member.comic_date or date.min,
        pk,
    )


def ordered_members(comics: dict[int, ArcMember]) -> list[tuple[int, ArcMember]]:
    """Return the arc's comics in list order."""
    return sorted(comics.items(), key=_sort_key)


def is_ordered(comics: dict[int, ArcMember]) -> bool:
    """Ordered when every comic has its own number, as comicbox decides."""
    numbers = [member.number for member in comics.values()]
    return None not in numbers and len(set(numbers)) == len(numbers)


def digest(comics: dict[int, ArcMember]) -> str:
    """Digest an arc's membership and numbering: the tags source's revision."""
    pairs = sorted(
        (pk, -1 if member.number is None else member.number)
        for pk, member in comics.items()
    )
    return sha1(dumps(pairs).encode(), usedforsecurity=False).hexdigest()


def one_arc_members(sort_name: str) -> dict[int, ArcMember]:
    """Read one arc's comics, each with its lowest number."""
    through = Comic.story_arc_numbers.through
    rows = through.objects.filter(
        storyarcnumber__story_arc__sort_name=sort_name
    ).values_list("comic_id", "storyarcnumber__number", "comic__date")
    members: dict[int, ArcMember] = {}
    for comic_pk, number, comic_date in rows:
        known = members.get(comic_pk)
        if known is not None and not _lower(number, known.number):
            continue
        members[comic_pk] = ArcMember(
            number=number, comic_date=comic_date, series="", issue="", year=None
        )
    return members
