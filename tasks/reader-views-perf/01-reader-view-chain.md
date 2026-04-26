# 01 — Reader view chain (`c/<pk>` GET)

The main reader request. Returns:

- `arc` — the selected arc (group + ids + index + count).
- `arcs` — all arcs the comic belongs to (series / volume / folder
  / story_arc).
- `books` — the prev / current / next book window inside the
  selected arc (1–3 books).
- `close_route` — the `last_route` from `SettingsBrowser` for the
  "back to browser" button.
- `mtime` — the max `updated_at` across the comic's arcs.

Hits the inheritance chain
`ReaderSettingsBaseView → ReaderParamsView → ReaderArcsView →
ReaderBooksView → ReaderView`.

## Files in scope

| File | LOC | Purpose |
| ---- | --- | ------- |
| `codex/views/reader/params.py` | 70 | Input validation, memoized `params` property, arc kwarg shape |
| `codex/views/reader/arcs.py` | 134 | Build the arc context (series / volume / folder / story_arc) |
| `codex/views/reader/books.py` | 181 | Build the prev / current / next book window |
| `codex/views/reader/reader.py` | 49 | Top-level view — assembles the response |

## Per-request cost shape

`ReaderView.get_object()` runs in this order:

```python
arcs, mtime = self.get_arcs()          # arcs.py — 1 Comic FK fetch + 1 StoryArc query + per-arc work
books = self.get_book_collection()     # books.py — 1 ACL+filter query + N rows materialized + per-book settings/bookmark
arc = {...}                            # in-memory dict assembly
close_route = self.get_last_route()    # 1 SettingsBrowser query (cached on view)
```

Estimated per-request query count:

| Phase | Queries | Notes |
| ----- | ------: | ----- |
| Params validation | ~1 | `SettingsReader` + `SettingsBrowser` lookups (cached on view; first hit only) |
| `_get_field_names` | 1 | `AdminFlag.objects.get(folder_view)` — see #2 |
| `get_arcs.Comic.objects.get` | 1 | Comic + select_related FKs |
| `_get_story_arcs` | 1–2 | `StoryArc.exists()` + main query |
| `get_book_collection._get_comics_list` | 1 | Filtered comics queryset (count + iteration) — see #1 |
| `comics.count()` | 1 | Separate COUNT query |
| `_append_with_settings` × 1–3 | 2–6 | `SettingsReader.first()` + `Bookmark.first()` per book |
| `get_last_route` | ~0–1 | Cached |

Total: **~8–13 queries per reader open**, plus the materialization
cost of the comics list (which scales with arc size — 100-issue
series materializes 100 rows).

## Hotspots

### #1 — `get_book_collection` materializes the entire arc to find prev/curr/next

`codex/views/reader/books.py:147-181`:

```python
def get_book_collection(self) -> dict:
    comics = self._get_comics_list()
    books = {}
    prev_book = None
    pk = self.kwargs.get("pk")
    for index, book in enumerate(comics):
        if books:
            books["next"] = self._append_with_settings(book)
            break
        if book.pk == pk:
            if prev_book:
                books["prev"] = self._append_with_settings(prev_book)
            book.filename = book.get_filename()
            self._selected_arc_index = index + 1
            self._selected_arc_count = comics.count()
            books["current"] = self._append_with_settings(book)
        else:
            prev_book = book
    ...
```

The docstring acknowledges the optimal SQL approach was rejected:

> Uses iteration in python. There are some complicated ways of
> doing this with `__gt[0]` & `__lt[0]` in the db, but I think they
> might be even more expensive.

Hand-waving aside, the actual cost shape:

- `_get_comics_list` returns a queryset filtered by ACL + arc
  membership + browser filters, with `prefetch_related` for
  story_arc_numbers, ordered by `arc_index, date, pk` (story arc)
  or `path, pk` (folder) or `sort_name, issue_number, ...`
  (series/volume).
- The `for index, book in enumerate(comics):` loop materializes
  every row up to and including the row AFTER the current pk.
- For a series with 100 issues, reading issue #5 materializes 6
  rows; reading issue #95 materializes 96 rows. Average across the
  series: 50 rows materialized per reader open.
- `comics.count()` (line 173) **fires a separate COUNT(*) query**
  even after iteration begins. The count is needed for the
  `index/count` display in the UI ("Issue 5 of 100"); it's not
  derivable from a partial iteration.

Mitigations (in order of preference):

- **Two targeted queries.** One LIMIT 1 query for the current comic
  (already known by pk), one ORDER BY ... DESC LIMIT 1 query
  filtered to "comics ordered before the current" (prev), and one
  ORDER BY ... ASC LIMIT 1 query for "comics ordered after the
  current" (next). Plus the existing `count()` for total. Three
  queries, three rows materialized — independent of arc size.
- **Window-function single query.** `Comic.objects.annotate(rank=Window(RowNumber(), order_by=...))` with a self-join to find the rank-of-current and pull the rank±1 rows. One query, but window functions on SQLite have edge cases with `partition_by` and SQL complexity. The two-targeted-queries approach is simpler.
- **Separate `count` from `prev/curr/next` fetch.** Even with
  the existing implementation, deferring `comics.count()` to a
  second query that runs only after the current is found avoids a
  scan when the user is on page 1.

**Severity: high.** The hottest of the reader chain. Wall-time scales
linearly with arc size. For a 100-issue series, dozens of rows
materialized on every reader open with all annotations + ordering.

### #2 — `AdminFlag.objects.get(folder_view)` fired per request

`codex/views/reader/arcs.py:33-37`:

```python
for field_name in _COMIC_ARC_FIELD_NAMES:
    if field_name == "parent_folder":
        efv_flag = (
            AdminFlag.objects.only("on")
            .get(key=AdminFlagChoices.FOLDER_VIEW.value)
            .on
        )
        if not efv_flag:
            continue
    ...
```

Same anti-pattern flagged in OPDS sub-plans 02 #6 and 04 #2. Reads
the admin flag uncached even though the request-scoped
`self.admin_flags` `MappingProxyType` (from
`SearchFilterView.admin_flags`) exposes `folder_view` as a dict
lookup.

Inherited via the chain:

```
ReaderArcsView → ReaderParamsView → ReaderSettingsBaseView → SettingsBaseView → ...
```

Whether `SettingsBaseView` exposes `admin_flags` needs verification.
If yes, the fix is `self.admin_flags.get("folder_view")`. If no,
the fix is to either (a) inherit the right mixin path that does, or
(b) wire the flag onto an instance-cached property at this level.

Mitigation: use `self.admin_flags["folder_view"]`. Single edit,
eliminates the query.

**Severity: medium.** One query saved per reader open. Same
cross-cutting pattern that ships through the perf project's other
view families.

### #3 — `_append_with_settings` fires 2 queries per book

`codex/views/reader/books.py:49-59`:

```python
def _append_with_settings(self, book):
    reader_auth = self._get_reader_settings_auth_filter()
    book.settings = SettingsReader.objects.filter(**reader_auth, comic=book).first()
    bookmark_auth = self.get_bookmark_auth_filter()
    book.bookmark = (
        Bookmark.objects.filter(**bookmark_auth, comic=book)
        .only("page", "finished")
        .first()
    )
    return book
```

For 1–3 books returned (prev / curr / next) that's 2–6 queries.

Mitigations:

- **Annotate per-book settings + bookmark on the comics queryset
  once.** `Comic.objects.annotate(my_settings=FilteredRelation(...))`
  + `select_related("my_settings")` would fold the per-book lookups
  into the main query.
- **Batch the 1–3 book pks into one query.** After
  `get_book_collection` knows which pks to attach data for, fire
  one `SettingsReader.objects.filter(comic_id__in=pks)` and one
  `Bookmark.objects.filter(comic_id__in=pks)`, then partition in
  Python. Drops 2–6 queries to 2 queries.

The first option is more elegant but trickier to compose with the
existing iteration-driven flow. The second is mechanical and clearly
correct. Land #1 first; #3 becomes obvious once #1 lands because
the prev/curr/next pks are known up front from the targeted queries.

**Severity: medium.** Always fires 2–6 queries; mechanical fix.

### #4 — `_get_story_arcs` parses datetime strings per row in Python

`codex/views/reader/arcs.py:67-95`:

```python
qs = qs.annotate(
    ids=JsonGroupArray("id", distinct=True, order_by="id"),
    updated_ats=JsonGroupArray(
        "updated_at", distinct=True, order_by="updated_at"
    ),
)
...
for sa in qs:
    arc = {"name": sa.name}
    ids = tuple(sorted(set(sa.ids)))
    updated_ats = (
        datetime.strptime(ua, _UPDATED_ATS_DATE_FORMAT_STR).replace(tzinfo=UTC)
        for ua in sa.updated_ats
    )
    mtime = max_none(EPOCH_START, *updated_ats)
    ...
```

`JsonGroupArray("updated_at", ...)` returns a JSON-encoded array of
timestamp strings (SQLite doesn't have native datetime types, so
the timestamps come back as ISO-ish strings). The Python code then
`strptime`s every string per row.

For a comic with N story arcs (typically 0–3), each having M
related rows... this is small. But the strptime cost adds up if
some users have heavily-tagged story-arc comics.

Mitigations:

- **Aggregate the max in SQL.** `Max("updated_at")` instead of
  `JsonGroupArray("updated_at", ...)` returns a single datetime per
  arc that Django converts to a Python datetime via the field's
  `from_db_value`. No string parsing.
- **Cache the format string `_UPDATED_ATS_DATE_FORMAT_STR`.** Already
  module-level; no win.

**Severity: low.** Cleanup-worthy; not a hotspot at typical
story-arc counts.

### #5 — `_get_field_names` checks the same admin flag inside a 3-iteration loop

Related to #2 — the admin-flag lookup is *inside* the
`for field_name in _COMIC_ARC_FIELD_NAMES:` loop (lines 30–47).
With `_COMIC_ARC_FIELD_NAMES = ("series", "volume", "parent_folder")`,
the AdminFlag query fires only when `field_name == "parent_folder"`
(the third iteration), so it's actually 1 query per request, not 3.
Still a candidate for hoisting once the cached lookup is in place
(via #2).

The other branch (`show.get(group)`) reads from
`self.get_from_settings("show", browser=True)`. That's a per-request
call but presumably memoized inside the settings layer. Confirm
during the implementation pass.

**Severity: trivial.** Closes with #2.

### #6 — `_set_selected_arc` walks `all_arc_ids` for intersect

`codex/views/reader/arcs.py:97-116`:

```python
def _set_selected_arc(self, arcs) -> None:
    arc = self.params["arc"]
    arc_group = arc["group"]
    requested_arc_ids = arc.get("ids", ())
    arc_id_infos = arcs.get(arc_group)
    all_arc_ids: frozenset[tuple[int, ...]] = (
        frozenset(arc_id_infos.keys()) if arc_id_infos else frozenset()
    )
    arc_ids = ()
    if arc_group == STORY_ARC_GROUP:
        if requested_arc_ids in all_arc_ids:
            arc_ids = requested_arc_ids
        else:
            for arc_ids in all_arc_ids:
                if requested_arc_ids.intersection(frozenset(arc_ids)):
                    break
    if not arc_ids:
        arc_ids = next(iter(all_arc_ids))
    ...
```

The `frozenset(arc_ids)` build inside the loop allocates per
iteration. For a story-arc with many disjoint groupings this is
O(N × M). N is small in practice (story-arc count per comic, usually
0–3) so this isn't a real hotspot.

Pre-build `frozenset(arc_ids)` per `all_arc_ids` entry once outside
the loop if cleanup-required. Otherwise leave.

**Severity: trivial.** Code health, not perf.

### #7 — `_get_comics_list` annotation pyramid

`codex/views/reader/books.py:99-145`:

```python
qs = qs.annotate(
    volume_number_to=(F("volume__number_to")),
    issue_count=F("volume__issue_count"),
    arc_pk=F(arc_pk_rel),
    arc_index=arc_index,
    mtime=F("updated_at"),
    has_metadata=ExpressionWrapper(
        Q(metadata_mtime__isnull=False), output_field=BooleanField()
    ),
)
```

Plus `annotate_group_names` (from `SharedAnnotationsMixin`) and
optional `sort_name_annotations` (from `_get_comics_annotation_and_ordering`).

Each annotation appears in the SELECT clause and the `ORDER BY`
clause. The query already runs against an indexed comic table so
the per-row cost is bounded.

The `arc_pk` and `arc_index` annotations are needed for the prev /
curr / next ordering — they should remain. The
`volume_number_to` / `issue_count` annotations are read in the
serializer; verify whether the reader serializer needs them on
prev/next (probably yes, for display).

**Severity: low.** Inherited query shape; auditing for fields that
prev/next entries don't actually need would slim the SELECT but
gains are small.

## Out of plan

- **The `_get_comics_filter` ACL composition.** `get_acl_filter`
  and `ComicFieldFilterView.get_all_comic_field_filters` come from
  the browser-views perf project's filter pipeline. Already
  audited; no reader-specific work.
- **The `SharedAnnotationsMixin.get_sort_name_annotations`.** Same.
- **`get_last_route`.** Trivial settings lookup, cached.
- **`Comic.get_filename`.** Cheap string assembly off the comic row.

## Open questions

- **Does the reader endpoint cache key safely scope per-user?** It
  serves per-user bookmarks/settings. A `cache_page(60)` wrap with
  `vary_on_cookie` would amortize the cost across rapid tab
  refreshes (e.g. mobile-app re-foreground). Same trade-off as
  OPDS Stage 2: 60 s of staleness vs. zero re-render cost. Worth
  scheduling as a separate item.
- **What's the actual comic page count distribution?** Determines
  how often the prev/curr/next iteration's worst-case (last comic
  in arc) fires.
- **What's the read-time hit pattern?** A single user opening one
  comic vs. browsing through many is a different cost shape.
  Production traffic data would clarify.
