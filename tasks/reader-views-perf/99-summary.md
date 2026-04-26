# Codex `codex/views/reader/` — Performance Plan

A prioritized, sequenced plan for improving the performance of every
view under `codex/views/reader/` while preserving existing behavior.
Based on a file-by-file audit of ~850 LOC across 6 source files.
Broken out into three sub-plans:

- [`00-meta-plan.md`](00-meta-plan.md) — methodology, surface map,
  inheritance chain.
- [`01-reader-view-chain.md`](01-reader-view-chain.md) — `c/<pk>`
  GET (params / arcs / books / reader inheritance chain).
- [`02-reader-settings.md`](02-reader-settings.md) — `c/settings`
  and `c/<pk>/settings` CRUD.
- [`03-reader-page.md`](03-reader-page.md) — `c/<pk>/<page>/page.jpg`
  page binary.

This document rolls all sub-plan findings into one ordered backlog.
Each item cites the sub-plan for the detailed "why" and code-level
specifics.

---

## 1. Executive summary — where the time is going

The reader inherits the full `BrowserView` filter / annotation
pipeline. Browser-views perf and OPDS-views perf already closed the
shared hotspots (ACL filter, search parse, m2m gating, caching).
That leaves three categories of reader-specific cost:

1. **Comicbox archive open on every page request.** The biggest
   single hotspot in the reader subsystem. A 200-page comic =
   200 archive opens per read-through. Sub-plan 03 #1.

2. **`get_book_collection` materializes the entire arc to find
   prev/curr/next.** A 100-issue series materializes up to 100 rows
   per reader open. Two targeted SQL queries (`__lt`/`__gt` LIMIT 1)
   would collapse to 3 rows. Sub-plan 01 #1.

3. **Caching at the route layer is disabled.** `c/<pk>` (reader),
   `c/<pk>/<page>/page.jpg` (page server-side), and
   `c/<pk>/settings` (settings) all run the full pipeline on every
   request. Adding `cache_page` + `vary_on_cookie` (mirroring OPDS
   Stage 2 / browser cover route) would amortize cold cost across
   tab refreshes.

Secondary cost centers (see ranked backlog):

4. **Per-book settings/bookmark queries.** `_append_with_settings`
   fires 2 queries × 1–3 books per reader open. Sub-plan 01 #3.
5. **Uncached `AdminFlag.objects.get(folder_view)` in
   `_get_field_names`.** Same anti-pattern as OPDS sub-plan 02 #6;
   needs `self.admin_flags["folder_view"]`. Sub-plan 01 #2.
6. **Per-scope name-lookup query in settings GET.** 1 extra query
   per non-trivial scope. Sub-plan 02 #1.
7. **Two-query get-or-create in settings.** Sub-plan 02 #2.

---

## 2. Ranked backlog

Each row includes severity, estimated effort, risk, and a link to the
sub-plan with the code-level analysis. Status is **all-open** at
this point — no implementation has started. Use ⏳ Open until items
land.

### Tier 1 — critical latency wins

| #   | Change | Sub-plan | Impact | Effort | Risk | Status |
| --- | ------ | -------- | ------ | ------ | ---- | ------ |
| 1   | **Pool / cache the open Comicbox archive per (comic, process, short TTL).** Reader page-turn pattern hits the same archive repeatedly within seconds; per-request open is wasted I/O. LRU bounded by file-descriptor / memory budget. Worker pool implications. | 03 #1 | **Very high** (page-turn perceived latency) | M-L | M | ⏳ Open |
| 2   | **Replace `get_book_collection` whole-arc iteration with two targeted LIMIT-1 queries.** One query for `prev` (`< current.order_by_value` ORDER BY ... DESC LIMIT 1), one for `next` (`> current.order_by_value` ASC LIMIT 1). The current is already known by pk. Plus the existing `count()` for the arc index. | 01 #1 | **High** (linear → constant w.r.t. arc size; saves dozens of rows per reader open on large series) | M | M | ⏳ Open |
| 3   | **Re-enable route caching on `c/<pk>` (`ReaderView`).** Wrap with `cache_page(60)` + `vary_on_cookie`. Mirrors OPDS Stage 2. Reader endpoint serves per-user state — Vary on Cookie scopes the cache key correctly. | 00 / 01 | **High** (every reader open currently re-runs the full pipeline) | S | M | ⏳ Open |

### Tier 2 — redundant work on every request

| #   | Change | Sub-plan | Impact | Effort | Risk | Status |
| --- | ------ | -------- | ------ | ------ | ---- | ------ |
| 4   | **Batch `_append_with_settings` queries.** After #2 lands, the prev/curr/next pks are known up front. One `SettingsReader.objects.filter(comic_id__in=pks)` + one `Bookmark.objects.filter(comic_id__in=pks)`, partition in Python. Drops 2–6 queries to 2. | 01 #3 | Medium (saves 0–4 queries per reader open) | S | L | ⏳ Open |
| 5   | **Replace `AdminFlag.objects.get(folder_view)` with `self.admin_flags["folder_view"]` in `_get_field_names`.** Same anti-pattern as OPDS sub-plan 02 #6. Eliminates 1 query per reader open. Verify `admin_flags` is exposed on the reader inheritance chain. | 01 #2 | Low (1 query per reader open; cumulative cross-cutting) | S | L | ✅ Stage 0 (reader doesn't inherit `admin_flags`; used local `cached_property` + hoisted the loop's `show` settings read — see [stage0.md #5](stage0.md#5--_get_field_names-hoists-settings--admin-flag-reads)) |
| 6   | **Add server-side caching to the page endpoint** (`cache_page(PAGE_MAX_AGE)` + `vary_on_cookie`). Mirrors the cover endpoint. Trade-off: page bytes are large (~100–500 KB per page); cache disk pressure is real. Measure first. Less critical once #1 lands. | 03 #5 | High if #1 doesn't land; Low if #1 does | S | M | ⏳ Open |
| 7   | **Fold the per-scope name lookup into the comic prefetch.** `_get_scope` for `s` / `f` scopes fires a separate `Model.objects.filter(pk).values_list("name")` query. `select_related("series__name", "parent_folder__path")` on the comic prefetch covers `s` and `f`; story_arcs need a separate one-shot query. | 02 #1 | Low (1–3 queries saved per multi-scope GET) | S | L | ⏳ Open |

### Tier 3 — batch-shaped redundancies

| #   | Change | Sub-plan | Impact | Effort | Risk | Status |
| --- | ------ | -------- | ------ | ------ | ---- | ------ |
| 8   | **Replace `JsonGroupArray("updated_at")` + Python strptime loop with `Max("updated_at")`.** Story-arc mtime computation parses datetime strings per row in Python. SQL aggregation returns a single datetime per arc that Django converts via the field's `from_db_value`. | 01 #4 | Low (cleanup; small wins on heavily-tagged story-arc comics) | S | L | ⏳ Open |
| 9   | **Convert two-query get-or-create to `Model.objects.get_or_create`.** `_get_global_settings` and `_get_or_create_scoped_settings` both filter-then-create. Django ORM has the atomic primitive. | 02 #2 | Low (saves 1 query on cold-create paths) | S | L | ✅ Stage 0 |
| 10  | **Cache `get_reader_default_params` at class load.** Pure model metadata; doesn't change at runtime. | 02 #4 | Trivial | XS | L | ✅ Stage 0 |
| 11  | **Audit `_get_comics_list` annotation pyramid for prev/next dead fields.** Annotations applied to every row in the iteration — but prev/next entries don't need the same level of detail as current. Slimming the SELECT shrinks per-row I/O. | 01 #7 | Low | S | M | ⏳ Open |

### Tier 4 — clean-ups / small wins

| #   | Change | Sub-plan | Impact | Effort | Risk | Status |
| --- | ------ | -------- | ------ | ------ | ---- | ------ |
| 12  | **De-duplicate `_get_bookmark_auth_filter` between `ReaderSettingsBaseView` and `BookmarkAuthMixin`.** Currently inlined in two places. | 02 #5 | Code health | S | L | ⏳ Open |
| 13  | **Pre-build `frozenset(arc_ids)` in `_set_selected_arc` once outside the loop.** Sub-plan 01 #6. Trivial. | 01 #6 | Trivial | XS | L | ✅ Stage 0 (also fixed a no-match correctness bug — see [stage0.md #13](stage0.md#13--pre-build-frozenset-in-_set_selected_arc)) |
| 14  | **Drop redundant `.distinct()` on the page-endpoint comic queryset.** `.get(pk=pk)` LIMIT 1 collapses duplicates anyway. | 03 #6 | Trivial | XS | L | ✅ Stage 0 |
| 15  | **Cache the (user, comic_pk) ACL decision** for the page endpoint. Per-process LRU keyed on the pair, 60-second TTL. Skips the per-page ACL check during a single read-through. | 03 #2 | Low-Medium (depends on ACL filter cost in profile) | S-M | M | ⏳ Open |

### Tier 5 — high-risk / needs investigation before scheduling

| #   | Item | Sub-plan | Status |
| --- | ---- | -------- | ------ |
| R1  | **Reader perf harness.** No baseline data exists for reader endpoints. Build one analogous to `tests/perf/run_opds_baseline.py` covering at minimum: reader endpoint cold, page endpoint cold (+ per file_type), settings GET multi-scope, page-turn warm. Without this, every Tier 1–2 item is opinion-driven. | 00 (meta) | ✅ Stage 0 (`tests/perf/run_reader_baseline.py` + `stage0-before.json`) |
| R2  | **Per-route hit distribution.** Reader `c/<pk>` is hit once per comic-open; page `c/<pk>/<page>/page.jpg` is hit per page turn. Need production traffic data to scope #1's cache window and #6's disk pressure. | 03 (open) | ⏳ Open |
| R3  | **Archive-open cost distribution.** CBZ vs. CBR vs. PDF. Determines whether #1 (archive cache) or #6 (response cache) is the higher-impact item, and whether each is worth landing. | 03 (open) | ⏳ Open |
| R4  | **Reader frontend prefetch behavior.** Whether the reader pre-fetches +1, +2, +3 ahead — or +N for chapter-view — shapes #1's cache strategy and TTL. | 03 (open) | ⏳ Open |
| R5  | **Worker pool implications for the archive cache.** Multi-worker Granian deployments multiply per-worker caches. Either the cache is shared across workers (sidecar / Redis / shared-memory) or the per-worker cache effectiveness drops linearly with worker count. | 03 (open) | ⏳ Open |

---

## 3. Suggested landing order

Mirrors the OPDS phasing: measure first, then land independent
low-risk wins, then tackle structural items.

### Phase A — "measure before you cut" (required prep)

- [ ] Build the reader perf harness (R1). Mirror the structure of
      `tests/perf/run_opds_baseline.py` — JSON-output flows that
      record cold + warm timings + query counts.
- [ ] Record baseline timings for: reader endpoint cold, page
      endpoint cold (CBZ + CBR + PDF; small + large), settings GET
      multi-scope.
- [ ] Sample production traffic distribution if possible (R2 / R3 /
      R4).

Without baselines, Tier 1 #1 (archive cache) is blocked because
the size and TTL of the cache depends on traffic shape. #2 and #3
are safe to land without traffic data — they're per-request
deterministic improvements.

### Phase B — high-value, low-risk per-request wins

Independent fixes that don't depend on Tier 1 #1 landing:

- **#5** (replace AdminFlag.objects.get with admin_flags cache) —
  single edit.
- **#9** (`get_or_create` for settings) — mechanical.
- **#10** (cache reader default params) — trivial.
- **#13**, **#14** — trivial cleanups.

Together: a handful of small PRs over 1–2 days. Verify with the
Phase A harness.

### Phase C — `get_book_collection` rewrite (Tier 1 #2 + Tier 2 #4)

Land #2 (two targeted LIMIT-1 queries) first. Once the prev/curr/next
pks are known up front, #4 (batch settings/bookmark queries) becomes
mechanical. Together they make the reader endpoint cold cost
constant w.r.t. arc size.

### Phase D — caching (Tier 1 #3) + #7

#3 is the highest-impact items in the reader plan after the page
endpoint:

1. Wrap `c/<pk>` with `cache_page(60)` + `vary_on_cookie`.
2. Verify with the Phase A harness that response correctness holds
   across users (no cross-user leakage; bookmark-position changes
   visible within TTL).
3. Land #7 (settings name-lookup batching) as a follow-on cleanup
   in the same phase.

### Phase E — page-endpoint optimization (Tier 1 #1 + Tier 2 #6 + Tier 4 #15)

This is the biggest-impact phase but also the highest-risk:

1. Confirm R3 / R4 / R5 are resolved.
2. Decide between #1 (archive cache) and #6 (response cache) based
   on archive-open cost vs. cache disk pressure measurements.
3. Land #15 (ACL decision cache) as a small win regardless.

### Phase F — clean-ups (Tier 3 + 4)

Land in any order. Each is a small, isolated PR.

---

## 4. Cross-cutting guidance

A few patterns surfaced in multiple sub-plans; addressing them at
the architectural level prevents recurrence.

### A. Uncached `AdminFlag.objects.get` is the wrong shape

`arcs.py:33-37`'s pattern is the same anti-pattern flagged in
the OPDS plan (sub-plan 02 #6, 04 #2) and fixed in OPDS Stage 0
Phase B #6. Any check that reads an `AdminFlag` must go through
`self.admin_flags`, the request-scoped `MappingProxyType` populated
by `codex/views/browser/filters/search/parse.py:197-211`. Never
query `AdminFlag` directly in a view body.

### B. Per-row Python parsing of SQL aggregate strings

`arcs.py:67-95`'s `JsonGroupArray("updated_at") +
strptime per row` is a SQLite-specific anti-pattern. SQLite stores
datetimes as ISO strings, but Django's ORM normally handles the
conversion via the field's `from_db_value`. Aggregations that
return raw strings bypass that hook. Prefer `Max(field)` /
`Min(field)` / similar SQL aggregates that yield typed Python
values directly.

### C. `get_or_create` over filter().first() + create()

`settings.py:114-117` and `:124-132` use the manual pattern. Django
ORM has `Model.objects.get_or_create(defaults={}, **lookup)` which
is atomic + race-condition aware. Use it.

### D. Whole-result-set materialization to find a window

`books.py:get_book_collection` materializes the entire arc just to
find the row with `pk == kwargs.pk`. The optimal pattern for
"window around a known row" in SQL is two targeted queries
(`__lt LIMIT 1` + `__gt LIMIT 1`) or a window function. The
docstring's "I think they might be even more expensive" argument is
backwards — materializing 100 rows is always more expensive than 3
LIMIT-1 lookups.

### E. Comicbox open is the dominant page-turn cost

`page.py:_get_page_image` opens the archive on every request. Any
real win on page-turn latency requires keeping the archive open
across requests within a session. The trade-offs (memory, file
descriptors, multi-worker deployment) make this a structural
investment rather than a localized refactor.

---

## 5. What this plan does NOT address

Out of scope for this pass:

- Views outside `codex/views/reader/` (browser, OPDS, admin, auth,
  etc.).
- Serializer-layer N+1 audit. The browser plan deferred its
  serializer audit to a separate handoff
  (`tasks/browser-views-perf/stage5e-handoff-serializer-audit.md`).
  When that audit lands, repeat for reader serializers in
  `codex/serializers/reader.py`.
- Frontend reader.
- Comicbox internals — page extraction, archive parsing, PDF
  rendering. Tuning belongs to the comicbox project.
- Schema changes (denormalization, new indexes, PRAGMA tuning).
- Librarian / scribe perf — including the bookmark-update task
  coalescing flagged in sub-plan 03 #3.

---

## 6. Quick-reference: hotspot → sub-plan index

| Code location | Hotspot | Sub-plan |
| ------------- | ------- | -------- |
| `codex/views/reader/page.py:63-64` | Comicbox open per page request | 03 #1 |
| `codex/views/reader/books.py:147-181` | Whole-arc iteration | 01 #1 |
| `codex/views/reader/arcs.py:33-37` | Uncached AdminFlag.get | 01 #2 |
| `codex/views/reader/books.py:49-59` | Per-book settings/bookmark queries | 01 #3 |
| `codex/views/reader/arcs.py:67-95` | Per-row strptime on `updated_ats` | 01 #4 |
| `codex/views/reader/settings.py:198-207` | Per-scope name lookup | 02 #1 |
| `codex/views/reader/settings.py:114-117` + `:124-132` | filter().first() + create() | 02 #2 |
| `codex/views/reader/settings.py:63-69` | `get_reader_default_params` rebuilt per call | 02 #4 |
| `codex/views/reader/settings.py:83-92` | Duplicated `_get_bookmark_auth_filter` | 02 #5 |
| `codex/views/reader/page.py:51-54` | ACL filter on every page request | 03 #2 |
| `codex/views/reader/page.py:31-46` | Async bookmark task per page hit | 03 #3 |
| `codex/views/reader/page.py:52` | `.distinct()` on single-row queryset | 03 #6 |
| `codex/urls/api/reader.py:19` | No `cache_page` on reader endpoint | 00 / 01 |
| `codex/urls/api/reader.py:20-24` | No server-side `cache_page` on page endpoint | 03 #5 |
| `codex/urls/api/reader.py:41-46` | No cache on settings endpoint | 02 (open) |
