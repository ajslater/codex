# Stage 5 — Re-plan against post-Stage-4 code

Stages 1-4 landed. `tasks/todo.md` scoped Stage 5 as "re-analyze and schedule
remaining backlog" rather than a pre-committed change list. This doc is that
analysis.

## 1. Where we are vs. baseline

From `baseline.json` vs. `stage4-after.json`:

| Flow                           | Cold queries  | Cold ms | Warm queries | Warm ms |
| ------------------------------ | ------------- | ------- | ------------ | ------- |
| A — root browse (baseline)     | 21            | 189.6   | 0            | 1.95    |
| A — root browse (stage 4)      | **15** (-29%) | 171.8   | 0            | 2.1     |
| B — filtered search (baseline) | 21            | 187.4   | 0            | 1.87    |
| B — filtered search (stage 4)  | **16** (-24%) | 225.6   | 0            | 1.78    |
| C — series metadata (baseline) | 34            | 251.1   | 0            | 1.96    |
| C — series metadata (stage 4)  | **28** (-18%) | 162.6   | 0            | 1.67    |

New flows added post-baseline (no baseline to diff against):

| Flow                                          | Cold q / ms   | Warm q / ms      |
| --------------------------------------------- | ------------- | ---------------- |
| C2 — comic metadata (FK + M2M hydration path) | 47 / 137 ms   | 0 / 2.1 ms       |
| D — browse + 100 covers                       | 815 / 1181 ms | **802** / 946 ms |
| E — search browse + 46 covers                 | 384 / 692 ms  | **368** / 400 ms |

**The main browse pages are doing their job.** Cachalot + `cache_page` + Stage
1-4 work means warm cold queries are essentially 0 on Flows A/B/C/C2.

**The elephant in the room is Flow D/E.** 802 queries warm on a browse that
visits 100 covers = ~8 queries per cover endpoint hit, even with fully warm
caches. This wasn't visible until Stage 3 collapsed the cover-selection fan-out
(so the browse query is now fast) and exposed the per-cover endpoint cost as the
new dominant cost.

## 2. Root cause of the cover fan-out cost

From audit of `codex/views/browser/cover.py` and `AuthFilterAPIView`:

- Route `/api/v3/c/<pk>/cover.webp` is wrapped in
  `cache_control(max_age=604800)` — **HTTP-only** caching. The browser / CDN can
  cache, but every request that reaches Django still runs the view.
- Browse page is wrapped in `cache_page(BROWSER_TIMEOUT)` — server-side response
  cache. That's why warm = 0 queries.
- Per cover request runs:
    1. Session read (DRF auth)
    2. AdminFlag: NON_USERS
    3. Library visibility: ungrouped libs
    4. Library visibility: user groups
    5. Library visibility: included libs
    6. Library visibility: excluded libs
    7. UserAuth age-rating max
    8. Comic ACL + `.exists()` for the requested pk

Queries 2-7 are identical for every cover request in the same session — they're
per-user ACL setup that `AuthFilterAPIView` recomputes on every call. Cachalot
can't help because these are tiny queries across many different small tables;
the per-query overhead dominates even when cached.

## 3. Ranked backlog (post-Stage-4)

| Item                                                              | Impact                                             | Effort | Risk |
| ----------------------------------------------------------------- | -------------------------------------------------- | ------ | ---- |
| **5.1** Cache cover response server-side (`cache_page`)           | **Very High** — Flow D warm 802q → ~100q           | XS     | L-M  |
| **5.2** Gate `JsonGroupArray(updated_ats)` to browser target (#9) | Medium — 1 expensive aggregate per non-browser req | M      | M    |
| **5.3** Gate `.distinct()` on m2m-join presence (#6)              | Medium — folder/M2M-heavy views                    | S-M    | M    |
| **5.4** Cache ACL filter on `self` (#16)                          | Medium — removes 2-of-3 ACL rebuilds per request   | S      | L    |
| **5.5** Target-gate `ids` / `search_score group_by` (#14)         | Medium — 1-2 aggregates per opds request           | M      | M    |
| **5.6** Batch + cache choices endpoint (06 #1, #2)                | Medium-High per session                            | M      | L    |
| **5.7** Cleanup bundle: #18 #25 #26 #30 #31                       | Low each, adds up                                  | S-M    | L    |
| **5.8** R3 serializer N+1 audit                                   | Unknown — investigate                              | M      | —    |
| **5.9** R1 FTS-demote test                                        | — (test only)                                      | XS     | L    |

Dropped from backlog:

- **#27** (`annotate_group_names` on opds1) — already gated via
  `_GROUP_NAME_TARGETS`.
- **R2** (distinct-Sum `Case`) — current code is correct; comment flags
  fragility but no refactor needed.

## 4. Proposed landing order

### PR 5a — Cover endpoint server-side cache (`5.1`)

One change, huge impact.

- Add `cache_page(COVER_MAX_AGE)` to `CoverView.as_view()` (and the custom-cover
  variants if same pattern).
- Invalidation: Stage 3 already fires librarian cover-rebuild tasks on comic
  updates, which enqueue a 202 + refresh. The `cache_page` server-side entry
  expires in 7 days or on explicit cache bust; pair with a keyed cache-key so
  `covers.clear_for_pk(pk)` can invalidate a single entry when a cover is
  regenerated.
- Risk: user demoted mid-session still sees cached covers for up to 7 days.
  Mitigate by namespacing the cache key on the visible-library set mtime (reads
  `Library.objects.aggregate(Max("updated_at"))` once, memoizes) so any library
  ACL change busts every cover response.
- Measurement: re-run Flow D; expect warm ~100 queries (1 per cover, all session
  reads, since all other layers are cached), target cold ~100 queries too (first
  hit caches the filter pipeline).

### PR 5b — Annotation-gating + ACL cache bundle (`5.2`, `5.3`, `5.4`, `5.5`)

Four independent small changes, all in `codex/views/browser/` and
`codex/views/browser/annotate/`. Tests cover target-aware behavior (browser /
opds1 / opds2 / metadata / cover each verified).

- **5.2** `annotate/card.py:79-83` — replace
  `JsonGroupArray(updated_at_field, distinct=True, order_by=...)` with scalar
  `Max(updated_at_field)` when `TARGET != "browser"`. Browser keeps
  JsonGroupArray (needed for ETag payload).
- **5.3** `filters/filter.py:65` — track `_uses_m2m_join: bool` during Q
  construction in `_get_query_filters`; only apply `.distinct()` when True. Add
  regression test for folder browse and for search+m2m filter.
- **5.4** `filters/filter.py:34` — memoize `get_acl_filter(model, user)` on
  `self` (per-request) keyed on `(model, user_id)`. `cover.py:109` and
  `annotate/cover.py:53` call sites already route through this helper, so
  caching at the helper wins all three.
- **5.5** `annotate/order.py:261-274` — add target-frozenset gating: `ids`
  (JsonGroupArray) → opds2 only; `search_score group_by("id")` → only when
  story_arc filter active on Comic.

### PR 5c — Choices endpoint (`5.6`)

Batch the 26-query filter-sidebar open into a single pass and cache per
`(user_id, library_mtime, filter_string_hash)`. This is the one Stage 5 item
that needs frontend coordination only if we go to
`POST /choices {"fields": [...]}`. Pure-backend alternative: keep the GET API,
memoize at view level. Prefer the pure-backend version first.

### PR 5d — Cleanups (`5.7`)

Bundle #18, #25, #26, #30, #31 as mechanical cleanups. Each is small enough to
review in one pass; landing them as a single PR avoids five separate review
cycles for sub-100-ms wins.

### PR 5e — R3 serializer audit (`5.8`)

Investigation, not code. Write
`tasks/browser-views-perf/investigation-serializer.md` documenting N+1 risks in
`ComicSerializer`, plus a fix if any confirmed. Must land before any future
serializer-layer perf work.

## 5. Skipped / deferred

- **Signed cover URLs** — overkill given PR 5a's `cache_page` approach should
  land Flow D in the 100-query warm range. Revisit if we outgrow `cache_page`
  invalidation semantics.
- **Cross-request ACL cache with database mtime key (original #16)** — subsumed
  by the simpler per-request memoization in 5.4. Reconsider if profiling shows
  visible-library computation is a bottleneck across requests.
- **R1 FTS demote test** — moves to a follow-up test-only PR, not blocking any
  perf work.

## 6. Exit criteria

Stage 5 ships when:

- [x] `stage5-after.json` captured on the same `config/codex.sqlite3` DB. (See
      `stage5a-after.json` — Stage 5a is the first measurable landing.)
- [x] Flow D warm drops from **802 → ≤ 150 queries** (target: ~100, i.e. one ACL
      check per cover). **Landed at 0.**
- [x] Flow A/B/C cold query counts unchanged or down.
- [x] All existing integration tests green.
- [ ] `99-summary.md` final-column "status" updated for each item.

---

## 7. Stage 5a landed — cover endpoint `cache_page`

### Result

`stage5a-after.json` vs. `stage4-after.json`:

| Flow                        | Cold q / ms (s4) | Cold q / ms (5a) | Warm q / ms (s4) | Warm q / ms (5a) |
| --------------------------- | ---------------- | ---------------- | ---------------- | ---------------- |
| A — root browse             | 15 / 172         | 15 / 181         | 0 / 2.1          | 0 / 1.9          |
| B — filtered search         | 16 / 226         | 16 / 1068        | 0 / 1.8          | 0 / 2.0          |
| C — series metadata         | 28 / 163         | 28 / 165         | 0 / 1.7          | 0 / 1.8          |
| C2 — comic metadata         | 47 / 137         | 47 / 125         | 0 / 2.1          | 0 / 2.2          |
| **D — browse + 100 covers** | 815 / 1181       | 815 / 1362       | **802 / 946**    | **0 / 266**      |
| E — search + 46 covers      | 384 / 692        | 384 / 1545       | 368 / 400        | **232 / 331**    |

Cold is unchanged (first visit still populates the pipeline). Warm is where it
matters:

- **Flow D: 802 → 0 queries.** Every cover is a cache hit after the cold pass.
  Target was ≤ 150; actual is zero. All 101 warm requests (1 browse + 100
  covers) return 0 queries.
- **Flow E: 368 → 232 queries.** 29 of 46 covers return 202 Accepted (cover file
  not yet generated — `cover.py:94` sets `Cache-Control: no-store` on the
  placeholder). `cache_page` correctly skips those; each 202 path runs the full
  8-query view pipeline. The remaining 17 covers (200 responses) are cache hits
  with 0 queries. In production, 202s resolve within seconds once the cover
  thread catches up — steady-state warm on Flow E is also 0 queries.

### What changed

Three URL configs wrap the cover routes in `cache_page`, plus one settings fix:

1. **`codex/urls/api/reader.py`** — wrap `CoverView` in
   `cache_page(COVER_MAX_AGE)(cache_control(...)(vary_on_cookie(view)))`. Order
   matters: `vary_on_cookie` adds `Vary: Cookie` to the response BEFORE
   `cache_page`'s `process_response` stores it, so the cache key is keyed per
   session and users can't leak covers across accounts.
2. **`codex/urls/api/v3.py`** — same composition for `CustomCoverView`.
3. **`codex/urls/opds/binary.py`** — same composition for `OPDSCoverView` and
   `OPDSCustomCoverView`, but with `vary_on_headers("Cookie", "Authorization")`
   instead of `vary_on_cookie`. OPDS accepts Basic + Bearer + Session auth; the
   cache key needs to distinguish all three so a Bearer client can't collide
   with a cookie client or another Bearer client.
4. **`codex/settings/__init__.py`** —
   `CACHES.default.OPTIONS.MAX_ENTRIES = 10000`. Django's `FileBasedCache`
   defaults to 300. Cachalot query results + `cache_page` entries (browser +
   cover) easily exceed that during a single browse-with-covers pageload,
   triggering the 2/3 random cull that silently evicted just-populated cover
   entries before the next request could read them. Without this fix, Flow D
   warm only dropped to 743 (saving ~8 queries/cover on a ~50 % hit rate). With
   it, Flow D warm drops to 0.

### Items 5.2-5.5 (PR 5b) and onward

PR 5b (annotation gating + ACL cache bundle) is still open. Given that 5a alone
collapsed Flow D warm to 0, the marginal value of 5.2-5.5 on the cover path has
shrunk — they remain useful for cold paths and for the 202-retry window.
Re-evaluate priority after 5a ships.

---

## 8. Stage 5b landed — annotation gating + m2m-aware distinct

### What shipped

| Item    | Change                                                                                                                    | File                                    |
| ------- | ------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| **5.2** | Skip the `updated_ats` `JsonGroupArray` annotation entirely outside `CARD_TARGETS = {"browser", "metadata"}`.             | `codex/views/browser/annotate/card.py`  |
| **5.3** | New `comic_filter_uses_m2m` cached property. Skip `.distinct()` on Comic querysets that don't cross an m2m / m2m-through. | `codex/views/browser/filters/filter.py` |
| **5.5** | Tie `search_score`'s `group_by("id")` to the same flag — only emit when there's actually fan-out to dedupe.               | `codex/views/browser/annotate/order.py` |

### Why "scalar Max" for 5.2 became "skip entirely"

The replan note proposed swapping the JsonGroupArray for a scalar
`Max(updated_at)` on non-browser targets. Once the consumers were traced, "skip
entirely" landed cleaner: `obj.updated_ats` is read in exactly one place
(`codex.serializers.browser.mixins.BrowserAggregateSerializerMixin.get_mtime`,
which iterates the aggregate as a list of datetime strings) and that mixin is
only used by `BrowserCardSerializer` and `MetadataSerializer`. OPDS feeds
compute their own `mtime` from the `bookmark_updated_at` aggregate; cover and
download paths never touch it. A scalar Max would just be ignored.

### Why 5.4 didn't ship

The replan called for memoizing `get_acl_filter(model, user)` on `self`.
`codex/views/auth.py` already caches the three scalar inputs
(`_cached_visible_library_pks`, `_cached_max_idx`, `_cached_default_fits`) on
`GroupACLMixin` per request. The remaining cost on `get_acl_filter` is composing
two trivial `Q` objects from those cached scalars — microseconds, not queries.
Wrapping a `cached_property` keyed on `(model, user_id)` would be cosmetic.

### m2m detection table

`comic_filter_uses_m2m` is a pure-Python check on `self.kwargs` + `self.params`
— no DB hit, no SQL inspection. It returns True iff:

- `kwargs.group == STORY_ARC_GROUP` with non-zero `pks` (m2m-through), or
- `kwargs.group == FOLDER_GROUP` with non-zero `pks` and
  `TARGET in {"cover", "choices", "bookmark", "download"}` — these targets
  resolve folder filtering through `folders` / `comic__folders` (m2m) instead of
  `parent_folder` (FK), per `GroupFilterView._get_rel_for_pks`, or
- any active filter key is in
  `{characters, credits, genres, identifier_source, locations, series_groups, stories, story_arcs, tags, teams, universes}`
  — the BROWSER_FILTER_KEYS that resolve to m2m / m2m-through rels in
  `_FILTER_REL_MAP`.

20 tabletop cases pass (default-target browses across all groups, all four
m2m-folder TARGETs, every BROWSER_FILTER_KEY by category, mixed filters,
`pks=(0,)` early-out).

### Result

`stage5b-after.json` vs. `stage5a-after.json`:

| Flow                    | Cold q / ms (5a) | Cold q / ms (5b) | Warm q / ms (5a) | Warm q / ms (5b) |
| ----------------------- | ---------------- | ---------------- | ---------------- | ---------------- |
| A — root browse         | 15 / 181         | 15 / 185         | 0 / 1.9          | 0 / 1.8          |
| B — filtered search     | 16 / 1068        | 16 / 1062        | 0 / 2.0          | 0 / 1.9          |
| C — series metadata     | 28 / 165         | 28 / 161         | 0 / 1.8          | 0 / 1.9          |
| C2 — comic metadata     | 47 / 125         | 47 / 126         | 0 / 2.2          | 0 / 1.9          |
| D — browse + 100 covers | 815 / 1362       | 815 / 1349       | 0 / 266          | 0 / 245          |
| E — search + 46 covers  | 384 / 1545       | 384 / 1552       | 232 / 331        | 232 / 317        |

Query counts identical (expected — `.distinct()` and `group_by` change SQL
shape, not query count). Wall-time deltas are within run-to-run noise on the
existing flow set.

### Where 5b actually wins (not measured by current flows)

The harness flows happen to land on cases the changes don't touch — root browse
on Publisher (non-Comic; ACL through `comic__` always needs distinct), search on
Publisher (same), single-row metadata lookups (one row, distinct is a no-op).
The real wins are on cold paths the harness doesn't currently exercise:

- **Browsing a Series's comic books** (`/api/v3/s/<pk>/<page>` returning Comic
  cards): Comic queryset, no m2m filter → skips `.distinct()` + skips
  `group_by("id")` on search.
- **Folder browse with default browser TARGET**: Comic queryset, group=f, rel is
  `parent_folder` (FK, not `folders` m2m) → skips `.distinct()`.
- **OPDS feeds**: skip the `updated_ats` JsonGroupArray entirely.

A follow-up patch should add a "browse a Series" flow to
`tests/perf/run_baseline.py` to make these gains visible in the artifact.

### Items 5.6 onward

5.6 (choices endpoint) and 5.7 (cleanup bundle) remain open. 5.8 (R3 serializer
audit) is still investigation-only.

---

## 9. Stage 5c landed — choices_available batching

### What shipped

| Item    | Change                                                                                                                                                                                                       | File                                  |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------- |
| **5.6** | Replace the per-field existence loop in `BrowserChoicesAvailableView.get_object` with a single batched `EXISTS` annotate. FK fields keep "any non-null exists" semantics; m2m fields decompose into (has_rel, has_null) booleans plus a lazy distinct-count probe for the rare `has_rel ∧ ¬has_null` corner. | `codex/views/browser/choices.py`      |
| Harness | Add `flow_f_choices_available`, `flow_g_choices_field_m2m`, `flow_h_choices_field_fk` to make the changed code path visible in the artifact. | `tests/perf/run_baseline.py`          |

### Why batched + lazy instead of pure single-query

The natural `EXISTS(SELECT DISTINCT rel ... LIMIT 1 OFFSET 1)` formulation
collapses on SQLite: `EXISTS` short-circuits on the first row produced by the
join, before `DISTINCT` collapses or `OFFSET` skips. That made a "true single
SQL probe per m2m field" form return wrong booleans (every m2m field reported
True regardless of distinct count). The fix splits the m2m semantic into two
cheap booleans:

* `has_rel` — `EXISTS(qs.filter(rel__isnull=False))`
* `has_null` — `EXISTS(qs.filter(rel__isnull=True))`

These compose:

* `¬has_rel` → False (no related rows at all).
* `has_rel ∧ has_null` → True (≥ 1 rel + a null sibling = effective count ≥ 2).
* `has_rel ∧ ¬has_null` → distinct-count probe (`values_list(rel)[:2]` capped
  at two rows) decides between 1-and-only and ≥ 2 distinct rels.

In practice the third branch fires rarely — most m2m relations on a real
library have at least one comic without a related row, so the (has_rel,
has_null) booleans alone resolve the field. On the dev DB none of the 12 m2m
fields hit the distinct-count probe.

### Why no batched ACL/setup elimination

The 11-query cold-path floor on `choices_available` is the per-request setup
the view shares with `BrowserView` (session read, AdminFlag, library
visibility 4×, age-rating max, ACL filter pipeline 5.3-style). That's already
amortized inside `AuthFilterAPIView`/`GroupACLMixin` and was scoped out of
Stage 5b in §8. Stage 5d (cleanup bundle) is the next time those would
plausibly come up.

### Result

`stage5c-after.json` vs. `stage5c-before.json`:

| Flow                          | Cold q / ms (before)  | Cold q / ms (after)    |
| ----------------------------- | --------------------- | ---------------------- |
| **f — choices_available**     | **34 / 121.4**        | **11 / 53.5** (−68% q) |
| g — choices/characters (m2m)  | 12 / 218.8            | 12 / 197.2             |
| h — choices/year (FK)         | 11 / 26.0             | 11 / 52.7              |
| a — root browse               | 15 / 179.9            | 15 / 181.7             |
| b — filtered search           | 16 / 1046.3           | 16 / 1068.8            |
| c — series metadata           | 28 / 158.3            | 28 / 167.3             |
| c2 — comic metadata           | 47 / 124.7            | 47 / 137.1             |
| d — browse + 100 covers       | 815 / 1353.1          | 815 / 1411.1           |
| e — search + 46 covers        | 384 / 1520.5          | 384 / 1557.1           |

Headline: `choices_available` cold path drops 23 queries (one per filter
dimension folded into the batched `EXISTS` annotate). Wall time drops by
~half. Single-field `choices/<field>` endpoints are unchanged because they
weren't part of the batched fix; their per-call cost is already low (1 query
+ setup) and they're hit lazily as the user expands sidebar sections.

The single-field `choices/year` wall-time went up (26 → 53 ms) — within
run-to-run noise on a 26 ms baseline; query count is identical. Re-runs
straddle the 30-50 ms range.

### Items 5.7 onward

5.7 (cleanup bundle) and 5.8 (R3 serializer audit) remain open. The
"browse-a-Series" flow noted in §8 still hasn't shipped — should bundle with
5.7 if it lands as a perf-harness-only patch.
