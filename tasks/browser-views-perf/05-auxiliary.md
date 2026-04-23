# Auxiliary Views — Performance Analysis

Covers `cover.py`, `download.py`, and `bookmark.py`. The `choices.py`
view is big enough to warrant its own plan — see
[`06-choices.md`](06-choices.md).

## Inventory

| File | LOC | Purpose |
|------|-----|---------|
| `cover.py` | 165 | Serves a single cover image (WEBP) for a comic / group / custom cover. Inherits from `BrowserAnnotateOrderView`. Called once per visible card in the grid. |
| `download.py` | 67 | Streams a ZIP archive of comic files for a group. Minimal ORM work. |
| `bookmark.py` | 70 | PATCH endpoint to mark comics read / finished. Bulk upsert via `BookmarkUpdateMixin`. |

---

## Hotspots

### 1. CoverView runs the full `BrowserAnnotateOrderView` pipeline per request — CRITICAL
**Path:** `cover.py:45-166`

The cover endpoint (`/api/v3/browser/<pks>/cover.webp`) is called once
per visible card. With 72 cards visible per page, that's 72 separate HTTP
requests. Each request:

1. Inherits from `BrowserAnnotateOrderView` (line 45).
2. Calls `get_group_filter()` (lines 56-76).
3. For dynamic covers (non-Comic models), runs `_get_dynamic_cover()`
   (lines 94-102):
   - `self.get_filtered_queryset(Comic)` — full filter pipeline with
     ACL, search, bookmarks.
   - `self.annotate_order_aggregates()` — expensive aggregations.
   - `self.add_order_by()` — complex ORDER BY.
   - `.only("pk")` — doesn't prevent the aggregations.

**Why it's slow:**
- Per-request filter pipeline: ~100-200 ms (ACL, group filter, search).
- Per-request cover I/O: ~50 ms (filesystem stat, possible generation).
- **72 × (100-200 ms) = 7.2-14.4 s** total cover-fetch time per first
  page load.
- `cache-control: max-age=604800` mitigates repeat loads but not the
  first, and invalidates on filter change.

**Proposed change:**
1. **Signed cover URLs** — main BrowserView pre-computes cover URLs with
   opaque tokens so the blob endpoint doesn't need to re-authorize.
2. **Defer dynamic cover computation** — for group covers (non-Comic),
   serve a static fallback (group placeholder) initially.
3. **Bypass annotation for cover queries** — add `for_cover=True` flag
   to `get_filtered_queryset()` to skip expensive aggregations (order
   aggregates, bookmark annotations). Cover needs only ACL + group
   filter + sort logic.

**Impact:** HIGH — 72 × ~500 ms saved = ~36 s saved per first page
load, roughly linearly reduced thereafter.
**Risk:** Medium — server-side caching requires invalidation; pre-computed
tokens must validate ACL correctly.

---

### 2. BookmarkView bulk update without write batching across concurrent requests — LOW
**Path:** `bookmark.py:20-70`

After bulk update, notifies via `_notify_library_changed()` (enqueues a
task on LIBRARIAN_QUEUE). No coalescing — multiple rapid updates enqueue
multiple notifications.

**Proposed change:**
1. Request-scoped notification deduplication — coalesce multiple updates
   in a single HTTP request cycle into one notification.
2. Client-side debouncing (500 ms) — frontend collects bookmark updates
   and sends one PATCH.

**Impact:** Low (~50-100 ms per multi-update session, mostly I/O to
notifier queue).
**Risk:** Low.

---

### 3. GroupDownloadView doesn't pre-filter for streaming efficiency — LOW
**Path:** `download.py:14-67`

Streams a ZIP of comics. Gets file paths from the filtered queryset,
then adds each to ZipStream. No streaming per-comic; full ZIP constructed
before sending for large sets.

**Proposed change:**
1. Stream ZIP incrementally using ZipStream's chunked mode.
2. Add size limits — reject > 5 GB downloads with clear error; offload
   to background task.

**Impact:** Low — marginal unless users frequently download > 500 MB.
**Risk:** Low — ZipStream supports chunking.

---

## Cross-cutting Observations

### Cover endpoint called N times per page load

On a 72-card grid:
- **72 HTTP GET requests** to `/api/v3/browser/<pks>/cover.webp`.
- Each runs full filter pipeline.
- First page load: **7-14 s of cover overhead**.
- Filter change invalidates cache → re-fetch all.

Mitigations currently in place:
- HTTP `cache-control: max-age=604800` (7 days).

**Recommended approach:**
1. **Signed cover URLs** — BrowserView pre-computes cover URLs so the
   blob endpoint serves cached files without re-authorizing.
2. **Serve from CDN** — if covers are immutable (keyed by comic PK +
   custom flag), push to S3 / CloudFront with long TTL.

### Cover fan-out compounds with other request fan-out

Every page-level user interaction triggers:
- 1 browser page query.
- Up to 72 cover queries (this plan).
- Up to 26 choices queries (see `06-choices.md`).

Batching cover and choices together could cut total request count by an
order of magnitude.

---

## Out of Scope / Deferred

1. **BrowserView main page** — separate sub-plan (01).
2. **Search (FTS5) performance** — separate sub-plan (03).
3. **Bookmark notification architecture** — separate sub-plan
   (notifier / librarian).
4. **Library ACL scoping** — audited in auth sub-plan.
5. **Frontend optimization** (batching, deduplication) — requires JS
   changes; coordinate with frontend.
6. **Cover generation parallelization** — librarian sub-plan; currently
   single-threaded.
7. **CustomCover model** — assumed minimal; audit separately if needed.
8. **Serializer overhead** — assumed DB-query-dominated; profile
   separately.
9. **Choices endpoint** — moved to [`06-choices.md`](06-choices.md).

---

## Summary

| Hotspot | Severity | Impact | Risk | Effort | Priority |
|---------|----------|--------|------|--------|----------|
| Cover endpoint (72 calls / page) | HIGH | **7-14 s / first load** | Medium | Medium | 1 |
| Bookmark notifications | Low | **50-100 ms** | Low | Low | 2 |
| Download streaming | Low | Marginal | Low | Low | 3 |
