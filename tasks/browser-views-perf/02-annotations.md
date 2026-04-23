# Annotations Subsystem — Performance Analysis

## Inventory

| File                                             | LOC | Purpose                                                                                                        |
| ------------------------------------------------ | --- | -------------------------------------------------------------------------------------------------------------- |
| `codex/views/browser/annotate/__init__.py`       | 2   | Marker file (empty)                                                                                            |
| `codex/views/browser/annotate/order.py`          | 275 | Order value, search score, child count, page count, bookmark_updated_at, filename, story_arc_number aggregates |
| `codex/views/browser/annotate/card.py`           | 84  | Group, group_names, file_name, has_metadata, updated_ats (final combined aggregates)                           |
| `codex/views/browser/annotate/bookmark.py`       | 117 | Bookmark page/finished aggregates, progress computation                                                        |
| `codex/views/mixins.py` (SharedAnnotationsMixin) | 112 | Cross-view sort_name and group_name annotations                                                                |

---

## Hotspots

### 1. Unconditional `JsonGroupArray` on every query — HIGH

**Path:** `codex/views/browser/annotate/card.py:79-83`

Annotates
`updated_ats = JsonGroupArray(..., distinct=True, order_by=updated_at_field)`
unconditionally on all queries. SQLite `JSON_GROUP_ARRAY` serializes every
timestamp in each group into a JSON string. The serializer's
`_get_max_updated_at()` (mixins.py:39-54) then re-parses this JSON per row on
serialization, splitting strings and parsing dates. This happens even for opds1
/ metadata / cover targets that never display mtime. Runs for all models and all
targets without gating.

**Proposed change:** Replace with `Max(updated_at_field)` scalar for non-browser
targets; for browser, consider computing Max once per page and passing via
serializer context rather than per-row JSON arrays.

**Estimated impact:** High | **Risk:** Medium

---

### 2. `annotate_order_aggregates` multi-step fan-out with unconditional annotations — MEDIUM

**Path:** `codex/views/browser/annotate/order.py:261-274`

Chains 9 annotation methods, each adding SELECT/GROUP BY columns. `ids`
(line 263) always annotates `JsonGroupArray` despite only opds2 needing it.
Annotation order is fragile: `_alias_sort_names` (line 265) must run before
`annotate_order_value` for Comic, relying on call sequence. Result: 15+ SELECT
columns for typical group queries even when most are never displayed.

**Proposed change:** Conditionally annotate only for consuming targets. For
opds2, gate `ids`. Defer non-card-display annotations for metadata target.

**Estimated impact:** Medium | **Risk:** Medium

---

### 3. `group_by("id")` on search_score unconditional — MEDIUM

**Path:** `codex/views/browser/annotate/order.py:205-215`

`_annotate_search_scores()` appends `.group_by("id")` when ordering by
`search_score`, forcing full re-aggregation. Comment admits this is to "fix
duplicates with story_arc" but applies globally. Only needed when Comic is the
result model and story_arc filter is active.

**Proposed change:** Check for story_arc in active filters before applying
group_by; gate to Comic model only.

**Estimated impact:** Medium | **Risk:** Low

---

### 4. `get_max_bookmark_updated_at_aggregate()` called 3× per-request — HIGH

**Path:** `codex/views/browser/annotate/order.py:195`, `bookmark.py:99-100`,
`group_mtime.py:80`

Same aggregate computed 2-3 times:

- First in `_annotate_bookmark_updated_at()` (order.py:195-196), which sets
  `self.bmua_is_max = Value(true/false)`
- Second in `annotate_bookmarks()` (bookmark.py:99-100) only if
  `not self.bmua_is_max`
- Third in `group_mtime.py:80`

No deduplication; each reconstructs the same
`Max(bookmark.updated_at WHERE user_id=?)` filter.

**Proposed change:** Cache computed aggregate on `self` after first call; reuse
in bookmark.py and group_mtime.

**Estimated impact:** High | **Risk:** Low

---

### 5. `_annotate_file_name` row-by-row string operations — MEDIUM

**Path:** `codex/views/browser/annotate/card.py:45-53`

Computes filename via `Right(path, StrIndex(Reverse(path), Value(sep)) - 1)`
using SQLite string functions per row. No index helps. Only needed when
`order_key == "filename"` or folder views, but currently computed for all Comic
rows via the card annotation path.

**Proposed change:** Gate strictly: only annotate `file_name` for folder view or
when the frontend truly needs it. Consider a denormalized `filename` column at
import time (already implicitly ordered by via `_alias_filename`).

**Estimated impact:** Medium | **Risk:** Low

---

### 6. `bookmark_page` Sum with complex multi-branch Case — LOW

**Path:** `codex/views/browser/annotate/bookmark.py:24-45`

Complex `Case(When...)` with `page_count` evaluation per row before Sum
aggregation. Comment (line 57) admits "distinct breaks this sum and only returns
one" indicating fragility. Only group models pay the cost.

**Proposed change:** Extract Case into separate alias before Sum; simplify
filter logic.

**Estimated impact:** Low | **Risk:** Medium

---

### 7. `bmua_is_max` annotation repeats scalar per row — LOW

**Path:** `codex/views/browser/annotate/order.py:198-203`

Annotates `bmua_is_max = Value(self.bmua_is_max)` on every output row.
Serializer reads once per group to decide mtime logic. Bloats SELECT with N
copies of a constant.

**Proposed change:** Pass via serializer context instead; serializer reads once
per page.

**Estimated impact:** Low | **Risk:** Low

---

### 8. `get_sort_name_annotations` creates multiple aliases unconditionally — LOW

**Path:** `codex/views/mixins.py:56-70`

Builds 3-4 sort_name F-expression aliases (publisher, imprint, series, volume)
per Comic query when `order_key == "sort_name"`. Aliases don't SELECT but cost
JOINs / appear in GROUP BY.

**Proposed change:** Gate to only the sort_name needed for the current
`parent_group`; skip for opds2 / reader where unused.

**Estimated impact:** Low | **Risk:** Low

---

### 9. `_annotate_has_metadata` aliases unindexed field — LOW

**Path:** `codex/views/browser/annotate/card.py:55-59`

Alias `has_metadata = F("metadata_mtime")` forces a nullable, unindexed field
into SELECT/GROUP BY. `metadata_mtime` is nullable and not indexed (see comic.py
index inventory).

**Proposed change:** Add a sparse index on `metadata_mtime` or cast to boolean
at annotation time so NULL-vs-non-NULL is the only work.

**Estimated impact:** Low | **Risk:** Low

---

### 10. `annotate_child_count` with necessary but expensive distinct — LOW

**Path:** `codex/views/browser/annotate/order.py:217-226`

`Count(rel__pk, distinct=True)` is necessary to avoid double-counting when
story_arc joins per child, but runs for all models. DISTINCT count in SQLite is
expensive on wide joins.

**Proposed change:** Profile a subquery alternative or denormalize child_count
at import.

**Estimated impact:** Low | **Risk:** Medium

---

### 11. `annotate_group_names` runs unconditionally for opds1 — LOW

**Path:** `codex/views/mixins.py:88-111`

Adds `{publisher_name, series_name, ...}` for browser, opds1, opds2, reader.
Verify if opds1 actually displays group names in its feed spec.

**Proposed change:** Check opds1 spec; gate if unnecessary.

**Estimated impact:** Low | **Risk:** Low

---

## Cross-cutting Observations

### Annotation Ordering Fragility

`_alias_sort_names()` must run before `annotate_order_value()` for Comic
(order.py:115 vs 245). No explicit ordering enforced; relies on call sequence in
`annotate_order_aggregates()`. Refactoring could silently break Comic sort_name
ordering.

### Unused Annotations by Target

`ids` (JsonGroupArray) always runs but only opds2 uses it. Browser card uses
`pk`. Metadata doesn't use `ids`. Clear opportunity for conditional annotation.

### Serializer Parsing Redundancy

`_get_max_updated_at()` (mixins.py:39-54) parses every JSON array string on
per-object serialization. No memoization. Could be done once at annotation time
or cached.

### Bookmark Aggregate Redundancy

Same `Max(bookmark_updated_at)` computed 2-3× per request. First call sets
`self.bmua_is_max`; second call (line 99) only if not max — yet no caching.

### Distinct Aggregates

`JsonGroupArray(..., distinct=True)` and `Sum(..., distinct=True)` both used.
Comment on line 57 admits distinct "breaks" some sums. Verify necessity.

---

## Out of Scope / Deferred

- **Serializer field mapping** — which annotations are actually consumed by each
  target.
- **browser.py call order** — whether `annotate_order` → `annotate_card` →
  order/limit sequence is optimal.
- **FTS5 query plan** — ComicFTSRank perf and GROUP BY interaction with
  story_arc (belongs to filters plan).
- **Bookmark model indexes** — whether bookmark (user_id, updated_at) are
  indexed.
- **Denormalization trade-offs** — cost/benefit of pre-computing updated_at,
  child_count, filename at import.
- **Group model metadata_mtime reliability** — why group models' own
  `updated_at` is not refreshed by bulk_update / bulk_create.

---

## Summary

Three high-impact optimizations:

1. **Replace `JsonGroupArray` with `Max()` scalar** for non-browser targets;
   compute mtime once per page, not per row (eliminates JSON serialization +
   per-row parsing overhead).
2. **Cache bookmark_updated_at aggregate** across order.py, bookmark.py, and
   group_mtime.py calls (eliminates 2 redundant aggregate computations).
3. **Gate annotations to consuming targets** — conditional `ids` (opds2 only),
   `filename` (order_key or folder only), `search_score` (only when needed),
   reducing SELECT bloat by ~30%.

Most other hotspots are either necessary (distinct counts, Case statements for
bookmark logic) or low-overhead (alias vs annotate toggle, sort_name lookups).
The wins are in redundancy elimination and target-specific gating.
