# Choices Views — Performance Analysis

Covers the two choices endpoints that back the filter sidebar. Split out
from [`05-auxiliary.md`](05-auxiliary.md) because the choices fan-out is
a distinct problem shape from the cover fan-out.

## Inventory

| File | LOC | Purpose |
|------|-----|---------|
| `choices.py` | 248 | Two views: `BrowserChoicesAvailableView` (returns a boolean map of which filter fields have any choices at all) and `BrowserChoicesView` (returns the actual list of values for one field). |

The two views share filtering infrastructure but diverge on the final
shape of the output: `Available` is a 26-key boolean map; the full
`Choices` view is a per-field list of `{pk, name}` tuples, one field per
HTTP request.

---

## Hotspots

### 1. `BrowserChoicesView` queries DISTINCT per field, not cached — HIGH
**Path:** `choices.py:188-248`

Frontend calls `/api/v3/browser/<pks>/choices/<field_name>` for each
filterable field (26+ in `BROWSER_FILTER_KEYS`). Each call:
1. Runs `get_filtered_queryset(Comic)` (line 231) — full ACL + search
   pipeline.
2. For M2M fields, calls `get_m2m_field_query()` (lines 193-222):
   - Queries the related model with DISTINCT on the Comic relation.
   - Checks if nulls exist with a **separate `.exists()` query** (line
     102, `does_m2m_null_exist()`).

**Why it's slow:**
- No caching — each choices request is a DB hit.
- 26 requests → 26 × the filter pipeline.
- N+1 for null checks (one `.exists()` per M2M field).
- ACL filter runs in every call despite library membership being
  near-static per user.

**Proposed change:**
1. **Cache per `(user_id, library_ids, active_filters)`.** Django
   cache key like `"choices:{user_id}:{lib_hash}:{filter_hash}"`, TTL
   one hour or signal-invalidated when the librarian finishes an
   import.
2. **Batch the endpoint.** Replace the per-field GET with a single
   POST: `POST /api/v3/browser/<pks>/choices {"fields": [...]}` returns
   all requested fields in one response. Frontend changes required.
3. **Pre-compute global choices at librarian startup.** Stable values
   (publisher, genre, language, country) can live in a JSON artifact
   that the librarian refreshes when imports complete.

**Impact:** High per session — 26 requests × ~200 ms pipeline = ~5 s
initial sidebar load; cache hits take it to single digits of
milliseconds.
**Risk:** Low — cache invalidation hooks onto the librarian's existing
sync-complete signal; batching is a frontend + backend coordinated change
but the behavior is identical.

---

### 2. `BrowserChoicesAvailableView` checks existence with multiple queries — LOW
**Path:** `choices.py:131-185`

Returns the boolean availability map. For each field:
1. `_is_m2m_field_choices_exists()` (line 142): queries M2M model with
   `.count()` (line 146).
2. If `count == 1`, runs **another** query to check for nulls (line 152).

So for 26 fields the worst case is ~52 queries just to populate a map
of booleans.

**Proposed change:** collapse the per-field checks into one SQL pass.
Either:
- A single query with `CASE WHEN` / conditional aggregates reporting
  per-field existence flags, or
- `EXISTS` subqueries combined in one SELECT, returning a single row of
  booleans.

**Impact:** Low-ish (~100-200 ms per request), but this endpoint fires
alongside #1 on sidebar open, so the two compound.
**Risk:** Low — pure SQL shape change; output stays identical.

---

## Cross-cutting observations

### Sidebar open = request storm

Opening the filter sidebar fires **both** choices endpoints. In the
worst case the browser issues:
- 1 `available` call → up to 52 internal queries.
- 26 `choices/<field>` calls → 26 × filter pipeline.

That's ~5 seconds of blocking activity before the sidebar populates.
Items #1 (caching + batching) and #2 (consolidated existence check)
together reduce this to two round-trips and a handful of queries.

### ACL recomputation dominates choices cost

Every choices call re-runs `get_acl_filter()`, which is itself multiple
queries. The 03-filters plan already proposes a cross-request ACL cache
(item #16 in `99-summary.md`). That change alone cuts per-choices cost
substantially — worth considering whether to land the ACL cache before
or alongside the batched choices endpoint.

### Stable vs. filter-dependent choices

Not all choices are filter-dependent:
- **Stable**: publisher list, genre list, country, language, age_rating
  options — they change only when comics are imported.
- **Filter-dependent**: characters / creators / tags / story_arcs —
  users expect them to narrow based on current filters.

Two-tier caching could exploit this:
- Global app-level cache for stable fields (invalidated on import
  complete).
- Per-user / per-filter cache for filter-dependent fields.

---

## Out of scope / deferred

- Frontend batching changes — requires coordinated JS work.
- Pre-computing choices at librarian level — librarian sub-plan, not
  browser-views.
- Choices response serialization — assumed to not be the bottleneck
  (`{pk, name}` tuples are cheap); profile if item #1 doesn't move the
  needle.

---

## Summary

| Hotspot | Severity | Impact | Risk | Effort | Priority |
|---------|----------|--------|------|--------|----------|
| Choices not cached (26 calls / sidebar open) | HIGH | **2-5 s / session** | Low | Medium | 1 |
| Choices existence checks | Low | **100-200 ms** | Low | Low | 2 |
