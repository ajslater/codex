# Codex `codex/views/browser/` — Performance Plan

A prioritized, sequenced plan for improving the performance of every view under
`codex/views/browser/` while preserving existing behavior. Based on a
file-by-file audit of ~4,300 lines across 36 files, broken out into six
sub-plans:

- [`00-meta-plan.md`](00-meta-plan.md) — how this analysis was organized
- [`01-core-browser-flow.md`](01-core-browser-flow.md) — main view, pagination,
  mtime, settings, breadcrumbs
- [`02-annotations.md`](02-annotations.md) — `annotate/` (card, order,
  bookmark) + `SharedAnnotationsMixin`
- [`03-filters.md`](03-filters.md) — `filters/` + search parsing + FTS
- [`04-metadata.md`](04-metadata.md) — `metadata/` detail view
- [`05-auxiliary.md`](05-auxiliary.md) — cover, download, bookmark
- [`06-choices.md`](06-choices.md) — choices / filter-sidebar endpoints

This document rolls all sub-plan findings into one ordered backlog. It is not an
implementation plan per change — each item cites the sub-plan for the detailed
"why" and code-level specifics.

---

## 1. Executive summary — where the time is going

Browser views have three dominant cost centers, in descending order of
cumulative latency across a typical session:

1. **Cover fan-out.** `/api/v3/browser/<pks>/cover.webp` is called once per
   visible card (72 cards per browse page is typical). Each call runs the full
   `BrowserAnnotateOrderView` pipeline — ACL + search + annotations + ORDER BY —
   just to pick which comic's cover to serve. First-page cover overhead: ~**7-14
   s** wall time per browse view, mostly parallelizable on the client but still
   server-bound. _(See 05-auxiliary #1.)_

2. **Metadata detail view query fan-out.** The metadata endpoint (group detail
   page) fires **~37-40 queries** per request — 1 M2M UNION followed by 11
   hydration queries, 7 FK queries, 7 FK `.first()` extractions, 4 per-level
   group queries, 3 chained annotation passes, and the main queryset. Batching
   these cuts query count by ~60 %. _(See 04-metadata.)_

3. **Main browse page: 9-11 queries per request, with cachalot
   self-invalidating.** Triple COUNT (one grouped, two post-paginator),
   always-on `libraries_exist`, page-mtime aggregate, and an _unconditional_
   settings write on every request (`params.py:60`) that invalidates cachalot
   rows. _(See 01-core-browser-flow.)_

Secondary cost centers:

4. **Unconditional `.distinct()` on every filtered queryset**
   (`filters/filter.py:65`) and **unconditional `JsonGroupArray` aggregates**
   (`annotate/card.py:79`, `annotate/order.py:263`). Both apply to all targets
   whether or not they need the behavior.
5. **Duplicated bookmark-Max aggregate** (3× per request across
   `annotate/order.py`, `annotate/bookmark.py`, `group_mtime.py`).
6. **Search parser re-runs on every request**, including every page of paginated
   results with the same query string. Lark + regex tokenizer, not cheap.
7. **Choices endpoint** — up to 26 un-cached queries whenever the filter sidebar
   opens.

Everything else is noise by comparison (single-digit-ms wins).

---

## 2. Ranked backlog

Each row includes severity, estimated effort, risk, and a link to the sub-plan
with the code-level analysis. "Impact" is a rough ordering, not a benchmark —
profiling must confirm before merging any change.

### Tier 1 — critical latency wins

| #   | Change                                                                                                                                                                                                                                                                           | Sub-plan                   | Impact                                                     | Effort | Risk |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ---------------------------------------------------------- | ------ | ---- |
| 1   | **Reduce cover endpoint pipeline cost.** Add a `for_cover=True` short-circuit to `get_filtered_queryset` that skips annotation / order aggregates. Alternatively pre-compute signed cover URLs in the BrowserView response so the cover endpoint never runs the filter pipeline. | 05-auxiliary #1            | **Very high** (saves seconds per page load × every browse) | M-L    | M    |
| 2   | **Batch metadata intersection hydrations.** Replace the 11 sequential `field.related_model.objects.filter(pk__in=pks)` calls in `metadata/query_intersections.py:126` with a single `prefetch_related` on the union result.                                                      | 04-metadata #1             | **High**                                                   | M      | M    |
| 3   | **Consolidate metadata value-field annotations.** Collapse the 3 sequential `_intersection_annotate()` calls in `metadata/annotate.py:144-164` into one.                                                                                                                         | 04-metadata #2             | **High**                                                   | S-M    | L    |
| 4   | **Remove triple COUNT in browser flow.** Use `paginator.count`/`len(object_list)` instead of extra `.count()` calls in `paginate.py:68,70`; benchmark grouped-COUNT alternatives for `browser.py:94`.                                                                            | 01-core-browser-flow #1,#3 | **High**                                                   | M      | M    |

### Tier 2 — redundant work on every request

| #   | Change                                                                                                                                                                                                                | Sub-plan                | Impact                                            | Effort | Risk |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------- | ------ | ---- |
| 5   | **Cache bookmark-Max aggregate on `self`.** Single computation in `annotate/order.py`, `annotate/bookmark.py`, `group_mtime.py`.                                                                                      | 02-annotations #4       | High                                              | S      | L    |
| 6   | **Gate `.distinct()` on m2m-join presence.** `filters/filter.py:65` — track `_uses_m2m_join` during Q construction; only apply `.distinct()` when needed.                                                             | 03-filters #1           | High                                              | S-M    | M    |
| 7   | **Memoize search parse result.** Add `functools.lru_cache(256)` to `search/parse.py::_preparse_search_query` keyed on `(text, is_admin, folder_view_flag)`; add `lru_cache` to `search/field/filter.get_field_query`. | 03-filters #3,#4        | Medium-High                                       | S      | L    |
| 8   | **Diff-save params.** `params.py:60` writes `SettingsBrowser` on every request even when unchanged — causes cachalot flush. Compare to stored and skip when identical.                                                | 01-core-browser-flow #9 | Medium (cachalot flush impact is the hidden cost) | S      | L    |
| 9   | **Replace unconditional `JsonGroupArray` `updated_ats` with scalar `Max`** for non-browser targets (`annotate/card.py:79-83`). For browser, compute Max once per page and pass via serializer context.                | 02-annotations #1       | High                                              | M      | M    |
| 10  | **Cache `libraries_exist`.** `browser.py:206` — cache signal-based or short-TTL.                                                                                                                                      | 01-core-browser-flow #2 | Medium                                            | S      | L    |

### Tier 3 — batch-shaped redundancies

| #   | Change                                                                                                                                                                                                                                             | Sub-plan                | Impact                  | Effort | Risk |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ----------------------- | ------ | ---- |
| 11  | **Batch metadata group through-model queries** into a UNION. `metadata/query_intersections.py:22-46`.                                                                                                                                              | 04-metadata #3          | Medium                  | M      | M    |
| 12  | **Batch metadata FK intersection queries** into a UNION and batch-extract with `.first()`. `metadata/query_intersections.py:71-79`, `copy_intersections.py:63-65`.                                                                                 | 04-metadata #4,#5       | Medium                  | M      | M    |
| 13  | **Batch choices endpoint.** Convert from 26 sequential GETs to one `POST /choices {"fields": [...]}`; cache per (user, library, filters). Frontend change required.                                                                                | 06-choices #1           | Medium-High per session | M      | L    |
| 14  | **Gate annotations to consuming targets.** In `annotate/order.py:261-274`: `ids` (JsonGroupArray) → opds2 only; `filename` → folder or `order_key == "filename"`; `search_score` `group_by("id")` → only when story_arc filter is active on Comic. | 02-annotations #2,#3,#5 | Medium                  | M      | M    |
| 15  | **Batch mtime endpoint queries.** `mtime.py:37-40` loops `get_group_mtime` per group; fold into one aggregate.                                                                                                                                     | 01-core-browser-flow #6 | Medium                  | M      | M    |
| 16  | **Cross-request ACL cache.** `filters/filter.py:34` calls `get_acl_filter` 7+ times per request; the underlying visible-libraries set changes rarely. Cache per `(user_id, library_max_updated_at)`.                                               | 03-filters #2           | Medium                  | M      | L    |
| 17  | **Cache page mtime.** `browser.py:141` — short-TTL cache per `(user, group, pks, params)` or denormalize.                                                                                                                                          | 01-core-browser-flow #4 | Medium                  | S-M    | L    |

### Tier 4 — clean-ups / small wins

| #   | Change                                                                                                            | Sub-plan                 | Impact     | Effort | Risk |
| --- | ----------------------------------------------------------------------------------------------------------------- | ------------------------ | ---------- | ------ | ---- |
| 18  | **Collapse `BrowserChoicesAvailableView` existence checks** into one SQL with `CASE WHEN`.                        | 06-choices #2            | Low        | S      | L    |
| 19  | **Pre-filter `get_all_comic_field_filters` loop** to active keys only. `filters/field.py:53-61`.                  | 03-filters #6            | Low        | S      | L    |
| 20  | **Cache `BaseDatabaseOperations(None)` at module level.** `search/field/expression.py:106`.                       | 03-filters #7            | Tiny       | XS     | L    |
| 21  | **Pull `bmua_is_max` off the row** (move to serializer context). `annotate/order.py:198-203`.                     | 02-annotations #7        | Low        | S      | L    |
| 22  | **Expand breadcrumbs `select_related`** to cover full FK chain per group type. `breadcrumbs.py:65-66`.            | 01-core-browser-flow #5  | Low-Medium | XS     | L    |
| 23  | **Only add `add_group_by` once.** `browser.py:88,117` — dedupe.                                                   | 01-core-browser-flow #7  | Low        | XS     | L    |
| 24  | **Guard `group_instance` query** on empty pks. `breadcrumbs.py:86-102`.                                           | 01-core-browser-flow #10 | Low        | XS     | L    |
| 25  | **Skip `sort_name` alias fan-out** beyond the current parent_group. `mixins.py:56-70`.                            | 02-annotations #8        | Low        | S      | L    |
| 26  | **Add sparse index on `metadata_mtime`** or cast to boolean at annotation time. `annotate/card.py:55-59`, models. | 02-annotations #9        | Low        | S      | L    |
| 27  | **Audit `annotate_group_names` for opds1.** Gate if opds1 spec doesn't use names. `mixins.py:88-111`.             | 02-annotations #11       | Low        | XS     | L    |
| 28  | **Remove dead code: `search/field/optimize.py`.** Unused per sub-plan analysis.                                   | 03-filters cross-cutting | Low        | XS     | L    |
| 29  | **Move multi-PK sum into main metadata queryset.** `metadata/__init__.py:52-97`.                                  | 04-metadata #6           | Low        | S      | L    |
| 30  | **Request-scope bookmark notification deduplication.** `bookmark.py:20-70`.                                       | 05-auxiliary #4          | Low        | S      | L    |
| 31  | **Incremental download streaming.** `download.py` — use ZipStream chunked mode.                                   | 05-auxiliary #5          | Low        | S      | L    |

### Tier 5 — high-risk / needs investigation before scheduling

| #   | Item                                                                                                                                                                                                             | Sub-plan          |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| R1  | **Conditional join demotion in `force_inner_joins`.** FTS5 semantics may depend on INNER JOIN; confirm with real FTS5 tests before touching.                                                                     | 03-filters #5     |
| R2  | **Replace distinct Sum bookmark `Case`.** The comment at `annotate/bookmark.py:57` ("distinct breaks this sum and only returns one") flags correctness risk; any refactor must reproduce the original semantics. | 02-annotations #6 |
| R3  | **Serializer audit for N+1.** `ComicSerializer` parent class may have `SerializerMethodField`s that trigger lazy FK access; out of scope for this plan but must happen before pushing metadata optimizations.    | 04-metadata #9    |

---

## 3. Suggested landing order

Work groups are designed to land independently so progress is visible without
long-lived branches.

### Phase A — "measure before you cut" (required prep)

- [ ] Wire `django-debug-toolbar` (already installed in dev?) or `django-silk`
      on a staging instance with realistic data.
- [ ] Record a baseline on three workloads: 1. Root browse (group='r', no
      search, no filters). 2. Filtered browse with search active. 3. Metadata
      detail page for a series with ≥ 10 comics.
- [ ] Benchmark grouped-COUNT vs alternatives for `browser.py:94` before
      touching it (item #4 has a benchmark risk).

Without baselines, Tier 2 and Tier 3 changes are hard to justify or verify. This
phase is ~1 day of work and pays for the rest of the plan.

### Phase B — high-value, low-risk wins (Tier 1-2 quick ones)

Target: measurable wall-time reduction on a browse page without significant
refactoring.

- Items **#5** (cache bookmark-Max), **#8** (diff-save params), **#10** (cache
  libraries_exist), **#20** (db ops cache), **#22-#24** (breadcrumbs / group_by
  / group_instance guards).
- Items **#19**, **#28** — pure cleanups.

These are independent and can land as a handful of small PRs over 1-2 days.

### Phase C — cover fan-out (Tier 1 #1)

Biggest user-visible win. Design options need a short discussion up front
(signed URLs vs pipeline-skip flag). Allocate a dedicated spike + PR. Needs a
cache-invalidation story.

### Phase D — metadata batching (Tier 1 #2, #3; Tier 3 #11, #12)

Interlinked set of changes in `metadata/`. Land in this order to keep each
change reviewable:

1. Consolidate `_intersection_annotate` (#3) — mechanical.
2. Batch M2M hydrations (#2) — biggest query-count win.
3. Batch group queries (#11) — pairs with #2.
4. Batch FK intersections (#12) — largest refactor; tests here matter.

Before starting, close **R3** (serializer audit).

### Phase E — filters subsystem (Tier 2 #6, #7; Tier 3 #16)

1. Memoize search parse (#7) — isolated, cheap.
2. Gate `.distinct()` (#6) — medium risk; needs search + folder regression
   tests.
3. Cross-request ACL cache (#16) — plan invalidation carefully.

### Phase F — annotations cleanup (Tier 2 #9; Tier 3 #14; Tier 4 #21, #25-#27)

Start with the mechanical target-gating (#14) and the serializer-context push
(#21), then tackle the `updated_ats` scalar switch (#9).

### Phase G — core flow & mtime (Tier 1 #4; Tier 3 #15, #17)

Triple-COUNT and mtime batching touch hot paths. Land after Phase B so the
baseline is clean.

### Phase H — choices and auxiliary (Tier 3 #13; Tier 4 #18, #30, #31)

Requires frontend coordination for #13; everything else is backend-only.

### Phase I — investigations (Tier 5)

Spin out `R1` (FTS demote test), `R2` (distinct-Sum refactor), `R3` (serializer
audit) as separate research tasks. Don't schedule implementation until the
investigation reports back.

---

## 4. Cross-cutting guidance

A few patterns surfaced in every sub-plan; addressing them at the architectural
level prevents recurrence.

### A. Target-aware annotations

`BrowserView.TARGET` is already the mechanism (values: `browser`, `opds1`,
`opds2`, `metadata`, `cover`, `reader`). Many annotations check `TARGET` inline.
Formalize this as a contract:

- Each `annotate_*` helper declares which targets it serves.
- A single dispatcher (probably on `BrowserAnnotateCardView`) only calls
  annotations whose target set includes `self.TARGET`.
- Removes scattered `if self.TARGET == ...` checks and the "did I remember to
  gate this?" risk at add time.

### B. Alias vs. annotate discipline

Current code mixes `alias` and `annotate` based on target. `alias` adds the
expression to the query plan (JOINs / GROUP BY / WHERE eligibility) without
SELECT. Rule of thumb for future PRs:

- **alias** if the value is only referenced in `filter` / `order_by`.
- **annotate** if the serializer or caller reads it.
- Never both.

### C. Cachalot-unfriendly write paths

Any write to `SettingsBrowser`, `SettingsBrowserFilters`, or `Bookmark` on the
read path will invalidate cachalot rows for those tables and cascade
invalidations to anything that joins them. Two observed instances:

- `params.py:60` — write on every browse (#8).
- Bookmark PATCH — necessary, but cluster notifications.

Tag any future code that writes on a read path with a comment noting the
cachalot impact, and consider adding a test that asserts no writes during a
plain GET.

### D. Search-string as a cache key

`self.params["search"]` is stable across pagination within a filtered view. Any
work that depends only on the search string — parsing, FTS token building, field
expression parsing — can be memoized off `(user_id, search_string, model_name)`.
This is the single cheapest optimization in the whole plan.

### E. Cover endpoint is the dominant cost at the _session_ level

Even a modest per-request cover-endpoint win compounds with 72 calls per page ×
N pages per session. When weighing a 5 % win on the browse page vs. a 20 % win
on the cover endpoint, prefer the cover.

---

## 5. What this plan does NOT address

Out of scope for this pass (per user instruction):

- Views outside `codex/views/browser/` (reader, admin, opds, auth, etc.). Expect
  some of the same patterns there.
- Serializer-layer work — SerializerMethodFields that trigger N+1 (flagged in
  04-metadata #9 as an investigation).
- Model/schema changes (denormalization, new indexes beyond `metadata_mtime`
  sparse index).
- Librarian/background task performance.
- Frontend perf (response caching, request batching, prefetching).
- Broader infra: connection pooling, SQLite PRAGMA tuning, CDN for covers.

---

## 6. Quick-reference: hotspot → sub-plan index

| Code location                                                       | Hotspot                          | Sub-plan  |
| ------------------------------------------------------------------- | -------------------------------- | --------- |
| `browser.py:94,117` `paginate.py:64-70`                             | Triple COUNT                     | 01 #1, #7 |
| `browser.py:141`, `group_mtime.py:85`                               | Page mtime aggregate             | 01 #4     |
| `browser.py:206`                                                    | `libraries_exist`                | 01 #2     |
| `breadcrumbs.py:65,124`                                             | Breadcrumb FK chain              | 01 #5     |
| `mtime.py:37-40`                                                    | Mtime endpoint batching          | 01 #6     |
| `params.py:60`                                                      | Diff-save params                 | 01 #9     |
| `annotate/card.py:79-83`                                            | `JsonGroupArray(updated_ats)`    | 02 #1     |
| `annotate/order.py:261-274`                                         | Annotation fan-out               | 02 #2     |
| `annotate/order.py:215`                                             | `group_by("id")` on search_score | 02 #3     |
| `annotate/order.py:195`, `bookmark.py:99`, `group_mtime.py:80`      | Duplicated bookmark Max          | 02 #4     |
| `annotate/card.py:45-53`                                            | Row-by-row filename              | 02 #5     |
| `annotate/bookmark.py:24-45,57`                                     | Distinct-Sum Case                | 02 #6, R2 |
| `filters/filter.py:65`                                              | Unconditional `.distinct()`      | 03 #1     |
| `filters/filter.py:13-21`                                           | `force_inner_joins`              | 03 #5, R1 |
| `filters/filter.py:34`                                              | ACL filter cache                 | 03 #2     |
| `search/parse.py:182-240`                                           | Search parse cache               | 03 #3     |
| `search/field/filter.py:96`                                         | Lark parse cache                 | 03 #4     |
| `filters/field.py:53-61`                                            | Loop-over-all-keys               | 03 #6     |
| `metadata/query_intersections.py:22-46`                             | Group queries                    | 04 #3     |
| `metadata/query_intersections.py:71-79`, `copy_intersections.py:63` | FK intersections                 | 04 #4, #5 |
| `metadata/query_intersections.py:105-129`                           | M2M hydrations                   | 04 #1     |
| `metadata/annotate.py:144-164`                                      | Value-field intersection calls   | 04 #2     |
| `metadata/__init__.py:52-97`                                        | Multi-PK sums                    | 04 #6     |
| `cover.py:45-166`                                                   | Cover pipeline                   | 05 #1     |
| `bookmark.py:20-70`                                                 | Bookmark notifications           | 05 #2     |
| `download.py:14-67`                                                 | ZIP streaming                    | 05 #3     |
| `choices.py:188-248`                                                | Choices uncached                 | 06 #1     |
| `choices.py:131-185`                                                | Choices existence checks         | 06 #2     |
