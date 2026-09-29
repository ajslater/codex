"""
Move existing anonymous settings rows that still hold the old site default.

Admin defaults are copied into a settings row when it is created. A
returning session-only visitor therefore keeps the defaults it was seeded
with. When the admin opts in on Save, the rows still holding the *old*
resolved default are moved to the new one, one conditional UPDATE per
changed field, so a visitor who changed one field keeps it while the others
move. Nothing is ever deleted, and saved views, scoped reader rows,
user-owned rows and OPDS rows are never touched.

``table_columns`` has no catch-up: it is never seeded, so rows already follow
the site default per collection at read time.
"""

from collections.abc import Iterable, Mapping, Sequence
from itertools import batched
from types import MappingProxyType
from typing import Any, Final

from django.db.models import Q, QuerySet
from django.db.models.functions import Now

from codex.choices.browser import SHOW_COLLECTIONS, admin_default_route_for
from codex.models.settings import (
    ClientChoices,
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserLastRoute,
    SettingsBrowserShow,
    SettingsReader,
)

_ANON_BROWSER: Final = MappingProxyType(
    {"user__isnull": True, "client": ClientChoices.API.value, "name": ""}
)
_ANON_READER_GLOBAL: Final = MappingProxyType(
    {
        "user__isnull": True,
        "client": ClientChoices.API.value,
        "comic__isnull": True,
        "series__isnull": True,
        "folder__isnull": True,
        "story_arc__isnull": True,
    }
)
# ``order_by`` first: its automatic-sort match reads each row's original top.
_DIRECT: Final = (
    "order_by",
    "order_reverse",
    "view_mode",
    "twenty_four_hour_time",
    "always_show_filename",
)
# The per-collection sort the settings GET fills in for an automatic ``""``.
_AUTO_SORT: Final = MappingProxyType(
    {"folders": "filename", "arcs": "story_arc_number"}
)
_AUTO_SORT_ANYWHERE: Final = ("", "sort_name")
# Top collections a row's show flags can never hide.
_ALWAYS_REACHABLE: Final = frozenset({"comics", "arcs", "folders"})
# Unseeded reader rows hold "" in the choice columns and null in the booleans.
_READER_BLANK: Final = MappingProxyType(
    {
        "fit_to": "",
        "reading_direction": "",
        "two_pages": None,
        "page_transition": None,
        "cache_book": None,
    }
)
_LAST_ROUTE_BATCH_SIZE: Final = 500
_EMPTY_ROUTE_PKS: Final = ([], [0])


def _anon_browsers() -> QuerySet:
    """Anonymous live API browser rows."""
    return SettingsBrowser.objects.filter(**_ANON_BROWSER)


def _anon_reader_globals() -> QuerySet:
    """Anonymous API global reader rows."""
    return SettingsReader.objects.filter(**_ANON_READER_GLOBAL)


def _match(field: str, old: Any) -> Q:
    """Rows still at the old value; the automatic sort counts as untouched."""
    if field == "order_by" and old == "":
        q = Q(order_by__in=_AUTO_SORT_ANYWHERE)
        for top_collection, auto in _AUTO_SORT.items():
            q |= Q(top_collection=top_collection, order_by=auto)
        return q
    return Q(**{field: old})


def _reader_match(field: str, old: Any) -> Q:
    """Reader rows at the old value, or never set at all."""
    blank = _READER_BLANK[field]
    if blank is None:
        return Q(**{field: old}) | Q(**{f"{field}__isnull": True})
    return Q(**{field: old}) | Q(**{field: blank})


def _show_q(show: Mapping[str, bool]) -> Q:
    """Rows whose show row has exactly these flags."""
    return Q(**{f"show__{c}": bool(show[c]) for c in SHOW_COLLECTIONS})


def _reachable(top_collection: str) -> Q:
    """Rows whose own show row keeps ``top_collection`` reachable."""
    if top_collection in _ALWAYS_REACHABLE:
        return Q()
    return Q(**{f"show__{top_collection}": True})


def _tops_reachable_in(show: Mapping[str, bool]) -> Q:
    """Rows whose top collection stays reachable under ``show``."""
    tops = [*_ALWAYS_REACHABLE, *(c for c in SHOW_COLLECTIONS if show[c])]
    return Q(top_collection__in=tops)


def _count(counts: dict[str, int], key: str, value: int) -> None:
    counts[key] = counts.get(key, 0) + value


def _apply_direct(browsers: QuerySet, old: Mapping, new: Mapping, counts) -> None:
    """One conditional UPDATE per changed direct field."""
    for field in _DIRECT:
        if old[field] != new[field]:
            counts[field] = browsers.filter(_match(field, old[field])).update(
                **{field: new[field]}, updated_at=Now()
            )


def _top_movers(browsers: QuerySet, old: Mapping, new: Mapping) -> list[int]:
    """
    Rows whose top will move, collected before any top UPDATE runs.

    Those at the old top that sit at the old show (the pair move) or whose
    own show keeps the new top reachable (the top-alone move).
    """
    old_top, new_top = old["top_collection"], new["top_collection"]
    if old_top == new_top:
        return []
    movers = browsers.filter(top_collection=old_top)
    if new_top not in _ALWAYS_REACHABLE:
        # ``Q() | q`` is just ``q``, so the always-reachable case can't be
        # spelled as an OR with ``_reachable``.
        movers = movers.filter(_show_q(old["show"]) | _reachable(new_top))
    return list(movers.values_list("pk", flat=True))


def _apply_show_and_top(browsers: QuerySet, old: Mapping, new: Mapping, counts) -> None:
    """
    Move show and top together, then each alone where it stays coherent.

    Rows at both old values move as a pair, so no row ends with a top its
    show hides. A single-field move checks the row's own show.
    """
    old_top, new_top = old["top_collection"], new["top_collection"]
    show_changed = old["show"] != new["show"]
    top_changed = old_top != new_top
    if not (show_changed or top_changed):
        return
    new_show, _ = SettingsBrowserShow.objects.get_or_create(**new["show"])
    pair = browsers.filter(_show_q(old["show"]), top_collection=old_top).update(
        show=new_show, top_collection=new_top, updated_at=Now()
    )
    if show_changed:
        _count(counts, "show", pair)
        _count(
            counts,
            "show",
            browsers.filter(_show_q(old["show"]), _tops_reachable_in(new["show"]))
            .exclude(top_collection=old_top)
            .update(show=new_show, updated_at=Now()),
        )
    if top_changed:
        _count(counts, "top_collection", pair)
        _count(
            counts,
            "top_collection",
            browsers.filter(_reachable(new_top), top_collection=old_top).update(
                top_collection=new_top, updated_at=Now()
            ),
        )


def _repair_last_route(moved: Sequence[int], old_top: str, new_top: str) -> int:
    """Point the untouched default last route of moved rows at the new top."""
    old_route = admin_default_route_for(old_top)["collection"]
    new_route = admin_default_route_for(new_top)["collection"]
    if not moved or old_route == new_route:
        return 0
    untouched = Q()
    for pks in _EMPTY_ROUTE_PKS:
        untouched |= Q(pks=pks)
    count = 0
    for batch in batched(moved, _LAST_ROUTE_BATCH_SIZE):
        count += SettingsBrowserLastRoute.objects.filter(
            untouched, browser_id__in=batch, collection=old_route, page=1
        ).update(collection=new_route, updated_at=Now())
    return count


def _apply_bookmark(old: Mapping, new: Mapping, counts) -> None:
    """Move the default bookmark filter on anonymous live browser rows."""
    if old["bookmark"] == new["bookmark"]:
        return
    browser_filter = {f"browser__{key}": value for key, value in _ANON_BROWSER.items()}
    counts["bookmark"] = SettingsBrowserFilters.objects.filter(
        bookmark=old["bookmark"], **browser_filter
    ).update(bookmark=new["bookmark"], updated_at=Now())


def _apply_reader(old: Mapping, new: Mapping, counts) -> None:
    """Move the anonymous global reader rows still at the old default."""
    readers = _anon_reader_globals()
    for field in _READER_BLANK:
        if old[field] != new[field]:
            counts[field] = readers.filter(_reader_match(field, old[field])).update(
                **{field: new[field]}, updated_at=Now()
            )


def apply_to_anonymous(
    old_browser: Mapping, new_browser: Mapping, old_reader: Mapping, new_reader: Mapping
) -> dict[str, int]:
    """
    Move anonymous rows that still hold the old default. Returns counts.

    ``old_*`` and ``new_*`` are resolver outputs from before and after the
    save: rows were seeded from the resolver, not the raw columns.
    """
    browsers = _anon_browsers()
    counts: dict[str, int] = {}
    _apply_direct(browsers, old_browser, new_browser, counts)
    moved = _top_movers(browsers, old_browser, new_browser)
    _apply_show_and_top(browsers, old_browser, new_browser, counts)
    if repaired := _repair_last_route(
        moved, old_browser["top_collection"], new_browser["top_collection"]
    ):
        counts["last_route"] = repaired
    _apply_bookmark(old_browser, new_browser, counts)
    _apply_reader(old_reader, new_reader, counts)
    return counts


def _counts_for(
    queryset: QuerySet, fields: Iterable[str], current: Mapping, match
) -> dict[str, int]:
    return {
        field: queryset.filter(match(field, current[field])).count() for field in fields
    }


def reach_counts(browser: Mapping, reader: Mapping) -> dict[str, int]:
    """Count anonymous rows still at each current resolved default."""
    browsers = _anon_browsers()
    counts = _counts_for(browsers, _DIRECT, browser, _match)
    counts["show"] = browsers.filter(_show_q(browser["show"])).count()
    counts["top_collection"] = browsers.filter(
        top_collection=browser["top_collection"]
    ).count()
    browser_filter = {f"browser__{key}": value for key, value in _ANON_BROWSER.items()}
    counts["bookmark"] = SettingsBrowserFilters.objects.filter(
        bookmark=browser["bookmark"], **browser_filter
    ).count()
    counts.update(
        _counts_for(_anon_reader_globals(), _READER_BLANK, reader, _reader_match)
    )
    return counts
