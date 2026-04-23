# Core Browser Flow — Performance Analysis

## Inventory

| File | LOC | Purpose |
|------|-----|---------|
| browser.py | 232 | Main entry point; orchestrates group/book queries, pagination, mtime probe |
| paginate.py | 73 | Paginates groups and books separately; calls .count() twice per request |
| page_in_bounds.py | 59 | Simple bounds checking; no queries |
| validate.py | 198 | URL route & settings validation; runs on every request via .model_group property |
| settings.py | 164 | BrowserSettings GET/PATCH/DELETE; validation logic for top_group/filters |
| saved_settings.py | 308 | Saved-settings endpoints; filter FK validation |
| breadcrumbs.py | 177 | FK chain walk for breadcrumbs; uses group_instance memoization |
| params.py | 68 | Parses query params + stored settings; saves last_route on every request |
| title.py | 50 | Fetches group_instance for page title |
| order_by.py | 76 | Resolves order key from params; no queries |
| mtime.py | 51 | Mtime endpoint for polling; calls get_group_mtime() per item |
| group_mtime.py | 97 | Computes Greatest(Max(comic.updated_at), Max(bookmark_updated_at)) per filtered queryset |
| const.py | 28 | Filter key constant definitions |

---

## Hotspots

### 1. Triple COUNT in main flow — CRITICAL

**Path:** `browser.py:88–94`, `paginate.py:64–70`

**What:** `BrowserView._get_common_queryset()` counts a grouped queryset
(line 94), returns the qs. Later, `paginate()` calls `.count()` on paginated
groups (paginate.py:68) and paginated books (paginate.py:70).

**Why it's slow:**
- Line 94: `count_qs.count()` where `count_qs = add_group_by(qs)[:limit]`
  runs a subquery: `SELECT COUNT(*) FROM (SELECT ... GROUP BY ...)`.
- Line 68: `page_group_qs.count()` re-counts the sliced queryset.
- Line 70: `page_book_qs.count()` counts books again.
- For a typical page with 20 groups + 10 books, this is 3 database
  round-trips in the count path alone.

**Proposed change:**
- After `paginator.page(page)` succeeds, use `len(paginator_page.object_list)`
  (which is free once the slice is evaluated) instead of `.count()`.
- Combine group and book counts before pagination using a single
  aggregate (COUNT(*) FILTER (WHERE is_book=0), COUNT(*) FILTER (WHERE
  is_book=1)) where possible.

**Estimated impact:** High (saves 2 COUNT queries per request)
**Risk:** Medium (paginator logic must be validated; off-by-one bugs in
slicing)

---

### 2. `libraries_exist` query runs on every browser request — HIGH

**Path:** `browser.py:206`

**What:** `Library.objects.filter(covers_only=False).exists()` fires a
query on every browser page load.

**Why it's slow:**
- Libraries change rarely (only on import/config).
- This is a textbook cache candidate: the answer is stable for hours/days.
- Even with cachalot hot, this is unnecessary chatter for a static value.

**Proposed change:**
- Wrap in an app-level cache keyed on Library change-signal (model
  `post_save`/`post_delete`) or simply a short-TTL cache (60s).
- Store in serializer context or request cache so computed once per
  request batch.

**Estimated impact:** Medium (saves 1 roundtrip per request; query is fast)
**Risk:** Low (cache invalidation on Library create/delete is trivial)

---

### 3. Grouped COUNT is heavier than flat COUNT — MEDIUM

**Path:** `browser.py:88–94`

**What:** After filtering, code calls `add_group_by(qs).count()` to get
the number of *groups*. This generates a subquery.

**Why it's slow:**
- Django's COUNT on a grouped queryset compiles to
  `SELECT COUNT(*) FROM (SELECT ... GROUP BY id, ...)`, not the
  optimized `SELECT COUNT(DISTINCT id)`.
- For querysets with many FKs and filters, the subquery plan can be
  expensive (full table scan + group, then count rows).

**Proposed change:**
- Benchmark: Compare `qs.values("pk").distinct().count()` vs
  `add_group_by(qs).count()`.
- Use the fastest alternative if semantics match.

**Estimated impact:** Medium (saves 10–50ms per request on large working
sets)
**Risk:** Medium (semantics of "count of groups" must be preserved)

---

### 4. Page mtime runs Greatest/Max aggregation on filtered queryset every request — MEDIUM

**Path:** `browser.py:141`, `group_mtime.py:65–96`

**What:** `_get_page_mtime()` calls `get_group_mtime(self.model,
page_mtime=True)`, which constructs a
`Greatest(Max(updated_at), Max(bookmark_updated_at))` aggregate and
forces inner joins.

**Why it's slow:**
- This aggregation runs *after* pagination, so it only touches the
  page's items, but:
- Bookmark aggregation (group_mtime.py:48–63) walks the bookmark
  relation with a filter — slow if many bookmarks exist.
- `force_inner_joins()` promotes all left-joins to inner, which can
  change join order and cost.

**Proposed change:**
- Cache the max mtime per (user, group, filters, limit) tuple for
  TTL ≈ 5–10 seconds.
- Or push mtime calculation to the frontend: send `max_updated_at` per
  item in the response and compute max there.

**Estimated impact:** Medium (saves 20–100ms per request)
**Risk:** Low (mtime is informational; frontend handles stale values)

---

### 5. Breadcrumbs FK chain walk — potential N+1 — LOW-MEDIUM

**Path:** `breadcrumbs.py:104–131`, especially line 124

**What:** `_build_group_breadcrumbs()` walks `_GROUP_PARENT_CHAIN` by
following FK attributes via `getattr`. The initial `group_instance` is
fetched with `select_related` (line 65–66), but the chain walk relies on
cached relations.

**Why it's slow:**
- If `group_instance` is not fully loaded, `getattr(gi, attr, None)`
  lazily loads the parent FK on line 124.
- For a deep hierarchy (Publisher → Imprint → Series → Volume → Comic),
  this is N+1 lazy loads.

**Proposed change:**
- Ensure `select_related` in `_get_group_query` (lines 65–66) covers the
  full chain, not just one level.
- For Volume, expand to `select_related("series", "imprint",
  "publisher")`.

**Estimated impact:** Low–Medium (saves 1–4 lazy queries per breadcrumb
walk)
**Risk:** Low (`select_related` is transparent)

---

### 6. Mtime endpoint re-computes `get_group_mtime()` for each group in request — MEDIUM

**Path:** `mtime.py:37–40`, `group_mtime.py:65–96`

**What:** `MtimeView.get_max_groups_mtime()` loops over
`self.params["groups"]`, calling `get_group_mtime()` per item. Each call:
- Runs `get_filtered_queryset()` with group/pks/page_mtime filter.
- Runs Greatest/Max aggregate.
- Calls `force_inner_joins()`.

**Why it's slow:**
- If a request includes 5 groups, that's 5 independent queries
  (5 × 50–100ms each = 250–500ms).
- No batching or reuse of filtered data.

**Proposed change:**
- Batch mtime queries: fetch all groups' data in a single pass, aggregate
  per group using CASE/WHEN or subquery.
- Or serve group mtimes with ETags so the client short-circuits.

**Estimated impact:** Medium (saves 4 roundtrips on mtime polling)
**Risk:** Medium (batching adds complexity; test with mixed group types)

---

### 7. `add_group_by()` called multiple times per request — LOW-MEDIUM

**Path:** `browser.py:88, 117`

**What:**
- Line 88: `add_group_by(qs)` for counting.
- Line 117: `add_group_by(qs)` again on the group queryset.

**Why it's slow:**
- `add_group_by()` modifies the query object; calling it twice creates
  two separate GROUP BY structures.
- Minor overhead, but unnecessary work.

**Proposed change:**
- Cache the grouped qs after the first call; reuse in
  `_get_group_queryset`.

**Estimated impact:** Low (saves milliseconds of Python time)
**Risk:** Low (grouping is deterministic)

---

### 8. Zero padding uses aggregate even when book_qs is empty — LOW

**Path:** `browser.py:130–138, 158, 182`

**What:** `_get_zero_pad(book_qs)` always aggregates Max(issue_number)
even if `book_count == 0`.

**Why it's slow:**
- Line 158 is inside `get_book_qs()` and is only called when
  `book_count`, so that's guarded. Line 182 guards as well.
- Still worth a re-audit: confirm there is no caller path that invokes
  `_get_zero_pad` on an empty book_qs.

**Estimated impact:** Low
**Risk:** Low

---

### 9. Params always saved to settings on every request — LOW

**Path:** `params.py:49–62`

**What:** `params` property calls `init_params()` →
`load_params_from_settings()` + serializer validation, then
`save_params_to_settings(params)` (line 60) and
`set_order_by_default(params)` (line 61).

**Why it's slow:**
- `save_params_to_settings()` unconditionally does a database write on
  `SettingsBrowser`/`SettingsBrowserFilters`.
- If params haven't changed, this is a wasted write — and each write
  invalidates cachalot entries keyed on those tables.

**Proposed change:**
- Diff the new params against the stored params; only save if changed.
- Or rely on field-level dirty tracking in Django ORM.

**Estimated impact:** Low raw time, but significant cachalot flush impact
**Risk:** Low

---

### 10. Breadcrumbs may run group_instance query even when not needed — LOW

**Path:** `breadcrumbs.py:86–102`

**What:** `group_instance` property is memoized but always fetches a
query (lines 93–101) even if breadcrumbs won't use it (e.g., root group
'r' with empty pks).

**Proposed change:**
- Guard the query fetch: check if `pks and 0 not in pks` before calling
  `_get_group_query`.

**Estimated impact:** Low
**Risk:** Low

---

## Cross-cutting observations

### Query count per typical browser request

1. Count groups (grouped): browser.py:94
2. Count groups again (paginated): paginate.py:68
3. Count books: paginate.py:70
4. Fetch group queryset + annotations: browser.py:179, 183
5. Fetch book queryset + annotations: browser.py:183
6. Max(issue_number) for zero-pad: browser.py:158, 182
7. Group instance (for breadcrumbs/title): breadcrumbs.py:101
8. Check libraries_exist: browser.py:206
9. Page mtime aggregate: browser.py:191, group_mtime.py:85–90
10. Bookmark aggregates if filtering by bookmark: group_mtime.py:48–63

**Total: 9–11 queries per request** (without caching). Cachalot caches
all of these, but the cache is invalidated when `SettingsBrowser` is
modified — which happens on every request thanks to hotspot #9.

### Cachalot effectiveness

- `CACHALOT_UNCACHABLE_TABLES = {"django_migrations", "django_session"}`.
- All Comic/Library/Volume queries are cached by default.
- **But:** every `params` save (`params.py:60`) invalidates
  `SettingsBrowser` row → all cached queries filtered by that row's
  params are invalidated.
- **Pattern:** filter change → SettingsBrowser update → broad cache
  invalidation → next page request misses cache.

### Memoization patterns (good)

- `validate.py` uses `@property` with underscore backing
  (`_model_group`, `_valid_nav_groups`, etc.).
- `breadcrumbs.py` uses similar pattern for `group_instance`.
- `order_by.py` memoizes `order_key`.
- `params.py` memoizes `self._params` after init.

### Join complexity

- `group_mtime.py:88` calls `force_inner_joins()`, which demotes LEFT
  JOINS to INNER.
- Necessary for search correctness (FTS matches must exist).
- Can change join order and cost; benchmark on real data.

### Cascade of properties

BrowserView → BrowserTitleView → BrowserBreadcrumbsView →
BrowserPaginateView → ... → BrowserOrderByView → BrowserGroupMtimeView →
BrowserFilterView.

Order matters: params loaded first, then `validate.valid_nav_groups`,
then `model_group`, then `group_instance`.

---

## Out of scope / deferred

- **Annotations** (annotate/ directory) — owned by separate plan.
- **Filters** (filters/ directory) — owned by separate plan.
- **Bookmark filtering logic** — performance depends on bookmark table
  size; owned by filters plan.
- **Custom order annotations** (mixins.py) — owned by annotations plan.
- **OPDS views** — inherit from browser; may have different hotspots.

---

## Summary Table

| Priority | Hotspot | Query Savings | Effort | Risk |
|----------|---------|---------------|--------|------|
| Critical | Triple COUNT (88–94, 68–70) | 2 queries | High | Medium |
| High | libraries_exist caching (206) | 1 query | Low | Low |
| Medium | Grouped COUNT semantics (88) | 0.5 queries | Medium | Medium |
| Medium | Page mtime caching (141) | 1 query | Low | Low |
| Medium | Mtime endpoint batching (37–40) | 4+ queries | High | Medium |
| Low | Breadcrumb select_related (65) | 0–4 queries | Low | Low |
| Low | Double add_group_by (88, 117) | 0.1 queries | Low | Low |
| Low | Zero-pad guard (130) | 0–1 query | Low | Low |
| Low | Params diff-save (60) | 0–1 write + cachalot flush | Low | Low |

**Estimated total savings:** 5–11 queries + 1–2 writes per request, or
25–50% reduction if all fixes stacked.

**Next steps:**
1. Profile with django-debug-toolbar on real workload to confirm query
   count.
2. Benchmark grouped COUNT vs alternatives.
3. Implement triple-COUNT fix first (highest impact).
4. Add `libraries_exist` cache (lowest risk).
5. Consider page mtime caching (medium impact, low risk).
