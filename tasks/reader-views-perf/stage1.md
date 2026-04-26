# Stage 1 — `get_book_collection` rewrite + per-book settings/bookmark batching

Closes Phase C from
[99-summary.md §3](99-summary.md#3-suggested-landing-order):

- **Tier 1 #2** — replace `get_book_collection`'s whole-arc Python
  iteration with a `values_list("pk")` materialization plus a
  targeted re-fetch for the 1-3 prev/curr/next rows.
- **Tier 2 #4** — batch `_append_with_settings`'s per-book
  `SettingsReader` + `Bookmark` lookups into two
  `filter(comic_id__in=…)` calls partitioned by comic_id.

Both items naturally land together — once #2 knows the prev/curr/next
pks up front, batching #4 is mechanical.

## Headline

`reader_open_large_arc`: **28 → 25 cold queries (-3)**, 89 → 52 ms
cold wall (**-42% wall-time reduction** on the 855-issue Batman
series).

| Flow                  | Cold queries (before → after) | Cold wall (before → after) |
| --------------------- | ----------------------------: | -------------------------: |
| **reader_open_large** |                  **28 → 25** |       **89 → 52 ms (-42%)** |
| reader_open           |                       26 → 25 |       49 → 51 ms (noise)   |
| (other 5 flows)       |               within ±0 noise |                            |

Artifacts: `tasks/reader-views-perf/stage1-before.json` and
`stage1-after.json`.

## What landed

### #2 — `get_book_collection` rewrite

`codex/views/reader/books.py:get_book_collection`. The prior
implementation iterated the entire arc-ordered queryset in Python
to find prev/curr/next:

```python
for index, book in enumerate(comics):
    if book.pk == pk:
        ...
        self._selected_arc_count = comics.count()  # extra COUNT query
        ...
```

For an 855-issue series with the user mid-arc, that's up to ~427
rows materialized with the full annotation pyramid (`sort_name`
aliases, `arc_index`, `has_metadata`, `volume_number_to`, …) just
to land on the current pk and pull its neighbors.

The rewrite uses the same arc-ordered queryset but materializes
only the pk integer column:

```python
pks = list(comics.values_list("pk", flat=True))
current_idx = pks.index(pk)
arc_count = len(pks)
prev_pk = pks[current_idx - 1] if current_idx > 0 else None
next_pk = pks[current_idx + 1] if current_idx + 1 < arc_count else None
```

Then re-fetches the 1-3 rows we actually need with the full
annotation pyramid:

```python
window_pks = [p for p in (prev_pk, pk, next_pk) if p is not None]
rows_by_pk = {row.pk: row for row in comics.filter(pk__in=window_pks)}
```

The `comics.filter(pk__in=…)` chain inherits all the annotations,
`select_related`, `prefetch_related`, and `only(*fields)` from the
parent queryset — so the 1-3 returned rows have everything the
serializer needs without re-deriving the queryset.

The `arc_count = len(pks)` replaces the prior separate `comics.count()`
query — saves another DB round-trip.

Cost analysis on the 855-issue arc:
- **Before:** 1 full-annotation SELECT returning ~427 rows + 1 COUNT
  query + 6 per-book queries (3 books × 2 lookups) = ~8 queries,
  ~427 fully-materialized Comic instances.
- **After:** 1 `values_list("pk")` SELECT returning 855 ints + 1
  full-annotation SELECT returning 1-3 rows + 2 batched per-book
  lookups = 4 queries, 858 ints + 1-3 Comic instances.

The Python work (855 int allocations + a `list.index(pk)`) is
microseconds; the DB ORDER BY still has to scan and sort the arc,
but the row data transfer is dramatically reduced.

### #4 — Per-book settings + bookmark batching

`codex/views/reader/books.py:_batch_settings_and_bookmarks`
(replaces the old `_append_with_settings`). The prior
implementation fired:

```python
SettingsReader.objects.filter(**reader_auth, comic=book).first()  # per book
Bookmark.objects.filter(**bookmark_auth, comic=book).only(...).first()  # per book
```

For 1-3 books that was 2-6 queries. Replaced with two batched
`filter(comic_id__in=window_pks)` calls partitioned by `comic_id`
in Python:

```python
settings_qs = SettingsReader.objects.filter(**reader_auth, comic_id__in=book_pks)
settings_by_pk = {s.comic_id: s for s in settings_qs}
bookmark_qs = Bookmark.objects.filter(**bookmark_auth, comic_id__in=book_pks)
    .only("page", "finished", "comic_id")
bookmarks_by_pk = {b.comic_id: b for b in bookmark_qs}
```

Always 2 queries regardless of book count — saves up to 4 queries
when the prev/curr/next window has all three slots filled.

## Verification

- **`make test`** — 24 / 24 pass.
- **`make lint`** — Python lint + typecheck pass; the
  `get_book_collection` is flagged at complexity rank C (down from
  the original's rank-C-with-iteration-state-machine — same letter
  grade, simpler logic).
- **Functional spot-check** — response shape preserved:
  - `arc.index` and `arc.count` match the prior implementation
    (verified on a small 4-issue series and an 855-issue series).
  - `books.prev` is absent for first issue; `books.next` is absent
    for last issue (verified both edges).
  - Per-book `settings` / `bookmark` / `filename` attributes
    attached as before.

## What's next

- **Phase D** — Tier 1 #3 (route caching on `c/<pk>`). Mirrors
  OPDS Stage 2. Highest-impact remaining structural item;
  amortizes the cold cost across tab refreshes / mobile-app
  re-foreground.
- **Phase D follow-on** — Tier 2 #7 (settings name-lookup
  batching).
- **Phase E** — Tier 1 #1 (Comicbox archive cache for page
  endpoint). Highest-risk; needs production traffic data before
  scheduling.
- **Phase F** — Tier 3 cleanups (#7, #8, #11, #12, #15).
