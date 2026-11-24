"""
Settings counted in registered users rather than in settings rows.

The ``sessions`` section counts rows, and codex writes a browser settings row
per user *and* per anonymous session. On any install with traffic that is
overwhelmingly anonymous sessions sitting on defaults nobody chose, so every
setting reads as near-unanimously default and says nothing about what people
prefer. These buckets count people instead.

Two families per surface, because the two product questions want different
denominators:

- **live / global** — one vote per user, so the buckets partition. ``""`` is a
  real key meaning "this user never touched the setting", and it is the point:
  a large untouched mass says the shipped default is at least tolerated, while
  the explicit choices beside it say what people move to when they care. This
  is the instrument for *are the defaults right*.
- **chosen** — every user who set a value anywhere, so the buckets overlap and
  never carry ``""``. A user who reads mostly left-to-right but sets ``rtl`` on
  some manga appears under both. This is the instrument for *does anyone use
  this option*, and it is deliberately not the same question: a value can be
  used by everybody occasionally and be nobody's main setting.

The browser filters get the second family only, as two buckets keyed by the
filter's name: the users who have each filter on anywhere, and the users who
set each tag-like filter to match all ticked values. What a filter is set to
is never selected: the query asks only whether the column is empty.

Privacy boundary: every key is a closed enum or a column name fixed in codex
source plus ``""``/``"true"``/``"false"``, and every value is a count of users
bounded by the registered user count already on the wire. Nothing here reads a
name, a path, or any per-user identity. No library-derived quantity is
computed, so nothing library-shaped can leak through a tie-break.

The section is always emitted when the collector runs, with zero counts when
there are no registered users -- never omitted. An absent section has to mean
"this codex is too old to send it", and chronicle learned the hard way what it
costs when "could not answer" is indistinguishable from "the answer is none".

Sampling is deliberately refused. Every query here is an aggregate whose result
is bounded by vocabulary size or user count, and a sampled answer would make
one install's weekly submissions disagree with each other under a stable UUID,
turning noise into apparent trend.
"""

from types import MappingProxyType
from typing import Any, Final

from django.db.models import Count, Q

from codex.choices.browser import BROWSER_MATCH_ALL_FILTERS
from codex.choices.reader import READER_DEFAULTS
from codex.models.settings import (
    ClientChoices,
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsReader,
)

# Browser settings worth asking about. Every one is non-null, so the only
# untouched marker among them is order_by's empty string.
BROWSER_FIELDS: Final[tuple[str, ...]] = (
    "top_collection",
    "order_by",
    "view_mode",
    "table_cover_size",
    "show_missing_issues",
)
# SettingsBrowserFilters columns that are not a filter of comics: bookkeeping,
# the settings row it belongs to, and the match-all switch list, which has a
# bucket of its own.
FILTER_BOOKKEEPING: Final = frozenset(
    {"id", "created_at", "updated_at", "browser", "match_all"}
)
_MATCH_ALL_FILTERS: Final = frozenset(BROWSER_MATCH_ALL_FILTERS)
# The match-all bucket for a stored name outside the vocabulary.
_OTHER: Final = "other"
# Ordered, unlike SettingsReader.DIRECT_KEYS which is a frozenset. A test pins
# the two to the same set so this cannot drift from the model.
READER_FIELDS: Final[tuple[str, ...]] = (
    "fit_to",
    "two_pages",
    "reading_direction",
    "page_transition",
    "cache_book",
)
# The value a field holds when nobody has touched it. Reader settings are all
# blank-or-null by default; among browser settings only order_by has one, and
# the rest ship a real value that an explicit choice is indistinguishable from.
# A row seeded from an admin site default (SettingsDefaults) stores that value,
# so an admin-chosen order_by counts here as the user's choice. Known, and
# deliberately left alone: telling the two apart would need per-row history.
BROWSER_UNTOUCHED: Final[MappingProxyType[str, str]] = MappingProxyType(
    {"order_by": ""}
)
UNTOUCHED: Final[str] = ""
# Returned for a field that is never "untouched" -- every stored value is a
# real choice, so nothing is excluded from its reach count.
_NO_MARKER: Final = object()

# Scope FKs on SettingsReader. All null means the row is the user's global one.
_SCOPE_FKS: Final[tuple[str, ...]] = ("comic", "series", "folder", "reading_list")
_GLOBAL_SCOPE: Final[Q] = Q(**{f"{fk}__isnull": True for fk in _SCOPE_FKS})


def _key(value: object) -> str:
    """
    Render a stored setting value as a bucket key.

    Booleans become "true"/"false" and None becomes "", so a nullable boolean
    and a blank char field say "untouched" in the same word. That is what lets
    one char-keyed bucket carry both, which is what chronicle stores.
    """
    if value is None:
        return UNTOUCHED
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _tally(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, dict]:
    """Count one vote per row for each field, keyed by the rendered value."""
    tallies: dict[str, dict] = {field: {} for field in fields}
    for row in rows:
        for field in fields:
            key = _key(row.get(field))
            tallies[field][key] = tallies[field].get(key, 0) + 1
    return tallies


def _chosen(queryset, fields: tuple[str, ...], untouched) -> dict[str, dict]:
    """
    Count distinct users per value, skipping each field's untouched marker.

    One GROUP BY per field. Distinct users rather than rows, so a reader who
    set right-to-left on fifty series counts once -- the question is how many
    people reach for a value, not how hard one person leans on it.

    ``untouched`` returns None for a field that has no untouched state, and
    that field is then counted whole. A sentinel value would have to survive
    Django's field validation on the way into the query, which it cannot.
    """
    chosen: dict[str, dict] = {}
    for field in fields:
        marker = untouched(field)
        rows = queryset if marker is _NO_MARKER else queryset.exclude(**{field: marker})
        rows = rows.values(field).annotate(users=Count("user_id", distinct=True))
        counts = {}
        for row in rows:
            key = _key(row[field])
            # Two stored values can render to one key only if the field is a
            # nullable boolean, whose None was already excluded. Summing is
            # still the safe reduction.
            counts[key] = counts.get(key, 0) + int(row["users"] or 0)
        chosen[field] = counts
    return chosen


def _pick_global(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """
    Reduce each user's global-scope rows to the one that speaks for them.

    There should be exactly one, but SettingsReader.folder is SET_NULL: delete
    a folder and its scoped row starts matching the global predicate. Prefer
    the row carrying the most set values, then the lowest pk, so an orphaned
    override never outranks a real global row and the answer is stable across
    submissions.
    """
    best: dict[int, dict[str, Any]] = {}
    for row in rows:
        user_id = row["user_id"]
        incumbent = best.get(user_id)
        if incumbent is None or _rank(row) > _rank(incumbent):
            best[user_id] = row
    return best


def _rank(row: dict[str, Any]) -> tuple[int, int]:
    """
    Order candidate global rows: most values set wins, then lowest pk.

    The pk is negated so one comparison covers both, and lowest-pk is the
    tiebreak rather than highest so the choice does not move when a later row
    is written.
    """
    return _set_count(row), -int(row["pk"])


def _set_count(row: dict[str, Any]) -> int:
    """How many reader fields this row actually sets."""
    return sum(1 for field in READER_FIELDS if _key(row.get(field)) != UNTOUCHED)


def _browser_stats() -> dict[str, Any]:
    """
    Browser settings, live row and reach.

    The live row is filtered to client=API and name="": the unique constraint
    is on (user, client, name), so named saved settings and OPDS rows are
    additional rows for the same user, and counting them here would break the
    one-vote-per-user partition. Reach deliberately drops both filters -- a
    value saved under any name or client is still someone using it.
    """
    live = list(
        SettingsBrowser.objects.filter(
            user__isnull=False, client=ClientChoices.API, name=""
        ).values("user_id", *BROWSER_FIELDS)
    )
    stats: dict[str, Any] = {"browser_user_count": len(live)}
    for field, counts in _tally(live, BROWSER_FIELDS).items():
        stats[f"browser_{field}_users"] = counts

    everywhere = SettingsBrowser.objects.filter(user__isnull=False)
    chosen = _chosen(
        everywhere,
        BROWSER_FIELDS,
        lambda field: BROWSER_UNTOUCHED.get(field, _NO_MARKER),
    )
    for field, counts in chosen.items():
        stats[f"browser_chosen_{field}_users"] = counts
    return stats


def _reader_stats() -> dict[str, Any]:
    """
    Reader settings, global row and reach.

    A user with reader rows but no global row votes "" everywhere: they have
    touched the reader without ever setting a global preference, which is
    exactly what the untouched key means.
    """
    rows = list(
        SettingsReader.objects.filter(user__isnull=False, client=ClientChoices.API)
        .filter(_GLOBAL_SCOPE)
        .values("pk", "user_id", *READER_FIELDS)
    )
    globals_by_user = _pick_global(rows)

    any_reader = SettingsReader.objects.filter(user__isnull=False)
    user_ids = set(any_reader.values_list("user_id", flat=True))
    scoped = any_reader.exclude(_GLOBAL_SCOPE).values("user_id").distinct().count()

    # Seed a fully-untouched row for every reader user without a global row, so
    # the histograms partition over the whole reader population rather than
    # over the subset that happens to have one.
    voters = [
        globals_by_user.get(user_id, {"user_id": user_id}) for user_id in user_ids
    ]

    stats: dict[str, Any] = {
        "reader_user_count": len(user_ids),
        "reader_scoped_user_count": scoped,
    }
    for field, counts in _tally(voters, READER_FIELDS).items():
        stats[f"reader_global_{field}_users"] = counts

    chosen = _chosen(any_reader, READER_FIELDS, _reader_untouched)
    for field, counts in chosen.items():
        stats[f"reader_chosen_{field}_users"] = counts
    return stats


def _reader_untouched(field: str) -> object:
    """Return the stored value that means "inherit" for one reader field."""
    return "" if isinstance(READER_DEFAULTS[field], str) else None


def filter_columns() -> dict[str, object]:
    """
    Map each browser filter column to the value it holds while it is off.

    Read off the model, so a new filter is counted without being listed
    here: an empty list for the multi-pick filters, "" for the bookmark
    choice.
    """
    return {
        field.name: field.get_default()
        for field in SettingsBrowserFilters._meta.concrete_fields
        if field.name not in FILTER_BOOKKEEPING
    }


def _match_all_users(rows) -> dict[str, int]:
    """
    Count the users who set each tag-like filter to match all ticked values.

    ``match_all`` holds filter names, not what a filter is set to. A stored
    name outside ``BROWSER_MATCH_ALL_FILTERS`` is counted under "other".
    """
    users: dict[str, set[int]] = {}
    switched = rows.exclude(match_all=[]).values_list("browser__user_id", "match_all")
    for user_id, names in switched:
        if not isinstance(names, list):
            continue
        for name in names:
            known = isinstance(name, str) and name in _MATCH_ALL_FILTERS
            users.setdefault(name if known else _OTHER, set()).add(user_id)
    return {key: len(user_ids) for key, user_ids in sorted(users.items())}


def _filter_stats() -> dict[str, Any]:
    """
    Browser filters in use, counted in users.

    A user counts toward a filter that is on in any of their settings rows:
    the live one, a saved view or OPDS. One count per column, and each asks
    only whether the column differs from its off value, so what a filter is
    set to never leaves the database. A filter nobody uses has no key.
    """
    rows = SettingsBrowserFilters.objects.filter(browser__user__isnull=False)
    in_use: dict[str, int] = {}
    for name, off in filter_columns().items():
        users = rows.exclude(**{name: off}).values("browser__user_id").distinct()
        if count := users.count():
            in_use[name] = count
    return {
        "browser_filter_users": in_use,
        "browser_match_all_users": _match_all_users(rows),
    }


def get_per_user_stats() -> dict[str, Any]:
    """
    Report browser and reader settings counted in registered users.

    Always returns the section. With no registered users every count is zero
    and every bucket empty, which is a different and more useful statement
    than sending nothing at all.
    """
    return _browser_stats() | _filter_stats() | _reader_stats()
