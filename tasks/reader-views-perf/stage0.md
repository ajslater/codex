# Stage 0 — Reader perf measurement + low-risk wins

Closes Phase A (R1: harness, R2: baseline) and Phase B (#5, #9, #10,
#13, #14) of the plan in
[99-summary.md §3](99-summary.md#3-suggested-landing-order).

## R1 — Reader perf harness

Built `tests/perf/run_reader_baseline.py`, mirroring the structure
of the existing OPDS / browser harnesses:

- Authenticates the synthetic `codex-perf` user via
  `Client.force_login`.
- Seven flows covering the three reader view families:
    - **Reader endpoint** (`c/<pk>`):
        - `reader_open` — busiest comic (richest M2M coverage).
        - `reader_open_large_arc` — middle issue of the busiest
          series; worst case for `get_book_collection`'s
          prev/curr/next iteration.
    - **Settings GET**:
        - `settings_global` — `?scopes=g`.
        - `settings_multiscope` — `?scopes=g,s,c`.
    - **Page binary** (`c/<pk>/<page>/page.jpg`):
        - `page_first` — page 0 of the high-page-count comic.
        - `page_middle` — middle page of the same comic.
        - `page_no_bookmark` — `?bookmark=0` to skip the librarian
          enqueue.
- Cold-then-warm methodology — `django_cache.clear()` +
  `cachalot.api.invalidate()` before each cold capture.
- Captures via `django-silk` so `num_sql_queries` and
  `time_taken_ms` come from the same instrumentation the OPDS /
  browser harnesses use.

Run with:

```
CODEX_CONFIG_DIR=$HOME/Code/codex/config DEBUG=1 \
  uv run python -m tests.perf.run_reader_baseline \
  --out tasks/reader-views-perf/<artifact>.json
```

## R2 — Baseline

Cold pass = the tracked metric (cachalot + django_cache invalidated
before each capture). Warm = the same request immediately
afterward. All on a populated dev DB:

- `series_pk_used = 325` ("All Batman", 106 comics) — busiest
  series; `busy_series_comic_pk` is its middle issue.
- `comic_pk_used = 10785` — busiest comic by character M2M.
- `high_page_pk_used = 157` (233 pages) — high-page-count comic
  for the page-binary flows.

| Flow                    | Cold queries | Cold wall (ms) | Warm queries | Warm wall (ms) |
| ----------------------- | -----------: | -------------: | -----------: | -------------: |
| reader_open             |           27 |             54 |           26 |             44 |
| reader_open_large_arc   |       **29** |        **110** |           28 |             60 |
| settings_global         |            4 |              9 |            3 |              6 |
| settings_multiscope     |            8 |             17 |            7 |             11 |
| page_first              |            9 |             17 |            8 |             11 |
| page_middle             |            9 |             16 |            8 |             11 |
| page_no_bookmark        |            9 |             19 |            8 |             10 |

The bold row is the headline target:

- **`reader_open_large_arc`** at 29 cold queries / 110 ms confirms
  [sub-plan 01 #1](01-reader-view-chain.md#1-get_book_collection-materializes-the-entire-arc-to-find-prevcurrnext)
  — the prev/curr/next iteration scales with arc size. Comic 10785
  in a 4-comic series shows 27 queries; the same shape on a
  middle-of-106-comic series shows 29 queries plus ~60 ms more
  wall time from materializing the larger arc.

`page_*` flows at 9 cold queries / 16 ms are dominated by the
Comicbox archive open (sub-plan 03 #1) — Comic.objects.get is just
1 of the 9 queries; the rest come from auth/session/ACL/admin-flag
plumbing.

`settings_multiscope` at 8 cold queries / 17 ms shows the
per-scope name-lookup pattern flagged in
[sub-plan 02 #1](02-reader-settings.md#1-per-scope-name-lookup-fires-its-own-query):
1 comic prefetch + 1 global + (1 scoped settings + 1 name) for `s`
+ 1 comic settings = 5 queries plus auth/session = 8.

## Phase B — what landed

Five plan items implemented; all "Tier 4 — clean-ups / small wins"
items per [99-summary.md §2](99-summary.md#2-ranked-backlog).

### #5 — `_get_field_names` hoists settings + admin-flag reads

`codex/views/reader/arcs.py`. Two changes in one function:

- **The `show` settings read was inside the loop.** Each non-folder
  iteration of `for field_name in _COMIC_ARC_FIELD_NAMES:` called
  `self.get_from_settings("show", browser=True)`, which fires a
  fresh `_load_browser_settings_data` query. With 2 non-folder
  iterations, that's 2 SettingsBrowser queries per call. Hoisted
  once outside the loop → 1 query.
- **The `AdminFlag.objects.get(folder_view)` lookup** is now a
  `@cached_property _reader_folder_view_enabled`. The reader chain
  doesn't inherit `SearchFilterView` (the OPDS / browser
  `self.admin_flags` source), so a local `cached_property` is the
  smallest equivalent — subsequent accesses within the same request
  are dict lookups; cachalot still caches the underlying SQL across
  requests.

Headline impact: 1 SettingsBrowser query saved per reader open
(27 → 26 cold). The plan's claim that `self.admin_flags["folder_view"]`
"eliminates the query" was based on the OPDS view's inheritance
chain; the reader chain doesn't have that ancestor, so the
equivalent fix is the `cached_property`. Documented in
[sub-plan 01 #2](01-reader-view-chain.md#2--adminflagobjectsgetfolder_view-fired-per-request).

### #9 — `get_or_create` over `filter().first() + create()`

`codex/views/reader/settings.py:_get_global_settings` and
`_get_or_create_scoped_settings`. Both used the manual two-query
pattern; replaced with `Model.objects.get_or_create(defaults=…,
**lookup)`. Same query count on the hit path, single atomic call
on the cold-create path.

The `defaults={}` is required to satisfy the typechecker on
`_get_or_create_scoped_settings` (the `**lookup` unpack would
otherwise be inferred as a candidate for the `defaults` parameter).

### #10 — `get_reader_default_params` cached at class load

`codex/views/reader/settings.py`. Decorated with
`@classmethod @cache`. Pure model metadata; doesn't change at
runtime. Saves the per-call dict-comprehension over
`SettingsReader.DIRECT_KEYS` plus the per-key `_get_field_default`
walks.

Caller-side note: `reset_reader_settings` uses the returned dict
as a read-only mapping (only iterates keys + reads values). No
mutation today, so the caching is safe. Docstring warns future
callers not to mutate the returned dict.

### #13 — Pre-build `frozenset` in `_set_selected_arc`

`codex/views/reader/arcs.py`. Two improvements rolled into one:

- The `requested_arc_ids` was being `frozenset(...)` cast
  per-iteration inside the inner loop. Hoisted to a single
  `requested_set = frozenset(requested_arc_ids)` outside the loop.
- **Drive-by correctness fix.** The original loop was:
  ```python
  for arc_ids in all_arc_ids:
      if requested_arc_ids.intersection(frozenset(arc_ids)):
          break
  ```
  After the loop, the `arc_ids` loop variable holds the
  matched value if `break` fired — but the LAST iterated value
  if no candidate matched. The subsequent `if not arc_ids:`
  fallback only triggered when `all_arc_ids` was empty (the loop
  never ran), not on no-match. Result: a no-match path returned
  whatever the iteration order happened to leave in `arc_ids`.
  Fixed by iterating to a separate `candidate` variable and only
  assigning `arc_ids = candidate` on match — fallback now fires
  correctly on no-match.

### #14 — Drop redundant `.distinct()` on the page-endpoint queryset

`codex/views/reader/page.py:_get_page_image`. The
`.distinct()` was paired with a comment ("Distinct is important")
but the next call is `.get(pk=…)` which is a single-row LIMIT 1
fetch — duplicates an ACL JOIN might introduce can't survive
that. Dropped; behavior unchanged.

## Headline numbers

| Flow                  | Cold queries (before → after) | Cold wall (before → after) |
| --------------------- | ----------------------------: | -------------------------: |
| **reader_open**       |                  **27 → 26** |       54 → 53 ms (noise)  |
| **reader_open_large** |                  **29 → 28** |       110 → 94 ms          |
| settings_global       |                         4 → 4 |        9 → 8 ms            |
| settings_multiscope   |                         8 → 8 |        17 → 13 ms          |
| page_first            |                         9 → 9 |       17 → 16 ms           |
| page_middle           |                         9 → 9 |       16 → 16 ms           |
| page_no_bookmark      |                         9 → 9 |       19 → 16 ms           |

The 1-query saving on `reader_open` / `reader_open_large_arc`
matches the SettingsBrowser hoist. `_set_selected_arc`'s frozenset
hoist + correctness fix doesn't change query count (no DB) but
removes a (theoretical) wrong-arc-on-no-match bug. The other
items are code-health refactors with no measurable per-request
impact.

The cleanup is intentionally modest. The big wins live in:

- **Phase C** — `get_book_collection` rewrite (Tier 1 #2) plus
  per-book settings/bookmark batching (Tier 2 #4). Together, the
  reader_open cost should drop from O(arc_size) to O(1) — the
  120 ms wall delta on the large_arc flow is the headroom.
- **Phase D** — route caching on `c/<pk>` (Tier 1 #3). Mirrors
  OPDS Stage 2.
- **Phase E** — page-endpoint Comicbox cache (Tier 1 #1). The
  hottest endpoint and the biggest single open question
  (production traffic data needed before scheduling).

## Verification

- **`make test`** — 24 / 24 pass.
- **`make lint`** — Python lint + typecheck pass; pre-existing
  remark warning on plan markdown unchanged.
- **Functional spot-check** — reader response shape preserved
  (`arcs`, `books`, `arc`, `closeRoute`, `mtime` keys all present;
  arc indices and counts match expected values).
- **Harness re-run** stable across two back-to-back captures.

## Plan / harness corrections worth noting

- The plan's sub-plan 01 #2 claimed `self.admin_flags["folder_view"]`
  was a one-line drop-in fix. The reader chain doesn't inherit that
  property; the fix had to introduce a local `cached_property`
  instead. Plan misjudgment — corrected in stage0.md but not
  rewritten in the original plan documents.
- Initial harness picked `comic_pk` (busiest by characters) for
  the `reader_open_large_arc` flow, but that comic happens to be
  in a 4-comic series rather than the busiest 106-comic series.
  Added `_busy_series_comic_pk(series_pk)` to pick a middle issue
  of the busiest series, so the flow actually exercises the
  worst-case prev/curr/next path. Reflected in the JSON artifact's
  `busy_series_comic_pk_used` field.

## What's next

- **Phase C** — Tier 1 #2 (`get_book_collection` rewrite) +
  Tier 2 #4 (per-book settings/bookmark batching). Highest-impact
  remaining structural item; biggest win on `reader_open_large_arc`.
- **Phase D** — Tier 1 #3 (route caching on `c/<pk>`). Mirrors
  OPDS Stage 2.
- **Phase E** — Tier 1 #1 (Comicbox archive cache for page
  endpoint). Highest-risk; needs production traffic data before
  scheduling.
- **Phase F** — Tier 3 cleanups (#7, #8, #11, #12, #15).
