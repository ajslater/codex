# Metadata Subsystem — Performance Analysis

## Inventory

| File | LOC | Purpose |
|------|-----|---------|
| `metadata/__init__.py` | 118 | Main `MetadataView`; orchestrates get_object(), annotates aggregates, queries intersections, copies results into Comic-like object |
| `metadata/annotate.py` | 165 | `MetadataAnnotateView`; batches intersection lookups via `_intersection_annotate()`, handles sum fields vs distinct-count fields |
| `metadata/const.py` | 86 | Constant tables: `SUM_FIELDS`, `COMIC_VALUE_FIELD_NAMES`, FK / M2M field lists, query optimizers map |
| `metadata/copy_intersections.py` | 88 | `MetadataCopyIntersectionsView`; post-query side effects (path security, group highlighting, copying querysets into object fields) |
| `metadata/query_intersections.py` | 138 | `MetadataQueryIntersectionsView`; queries FK & M2M intersections, batches group through-model queries |

---

## Hotspots

### 1. M2M intersection hydration — 11 sequential queries after UNION — HIGH
**Location:** `query_intersections.py:105–129`

The code correctly batches through-table queries into a single UNION,
but **re-hydrates the relations sequentially** (line 126):

```python
for field in COMIC_M2M_FIELDS:
    pks = pk_map.get(field.name, [])
    qs = field.related_model.objects.filter(pk__in=pks)   # 11 separate queries
    m2m_intersections[field.name] = self._get_optimized_m2m_query(qs)
```

Fields affected: characters, genres, credits, identifiers, locations,
series_groups, stories, story_arc_numbers, tags, teams, universes,
folders — 12 M2M relations on Comic.

**Impact:** ~11 additional queries after the union. Total: 1 UNION + 11
hydrations.

**Proposed fix:** Prefetch the related models as a batch after the UNION
using a single `prefetch_related()` on the union result instead of 11
separate filter cycles.

**Impact:** HIGH — 11 queries → 1 prefetch. ~10-15ms per metadata request.
**Risk:** Medium — refactoring union result into a prefetch structure
requires careful handling of the pk_map partitioning.

---

### 2. Value / FK intersection annotations — triple-counted distinct checks — MEDIUM
**Location:** `annotate.py:144–164`

Three separate `_intersection_annotate()` calls, each firing its own
COUNT(DISTINCT) pass:

```python
if qs.model is not Comic:
    querysets = self._intersection_annotate(querysets, comic_value_fields)
    querysets = self._intersection_annotate(
        querysets, COMIC_VALUE_FIELDS_CONFLICTING, ...
    )
_, qs = self._intersection_annotate(querysets, COMIC_RELATED_VALUE_FIELDS)
```

Each `_intersection_annotate()` fires:
- Query 1: `aggregate(Count(field, distinct=True) for field in ...)`
- Query 2: `values_list(*fields).first()` to fetch shared values

**Impact:** 3 annotation chains = ~6 queries instead of 1.

**Proposed fix:** Consolidate all value fields into one
`_intersection_annotate()` call, pre-partitioning into sum vs.
distinct-count groups within that single call.

**Impact:** Medium — 6 queries → 2.
**Risk:** Low — purely refactoring batch boundaries.

---

### 3. Group through-model queries — per-model sequential loops — MEDIUM
**Location:** `query_intersections.py:22–46`

```python
for model in GROUP_MODELS.get(group, ()):
    qs = model.objects.filter(**group_filter)
    qs = qs.only(*only).distinct().group_by(*only)
    qs = qs.annotate(ids=JsonGroupArray("id", ...))
    groups[field_name] = qs
```

Fields affected by group type:
- group='i': 1 query (Publisher)
- group='s': 2 queries (Publisher, Imprint)
- group='v': 3 queries (Publisher, Imprint, Series)
- group='c': **4 queries** (Publisher, Imprint, Series, Volume)
- group='f': **4 queries** (same hierarchy, folders)

**Proposed fix:** Merge `GROUP_MODELS` queries into a single UNION with
one `JsonGroupArray()` over all models, partition by model type in
Python.

**Impact:** Medium — 4 queries → 1 UNION (with careful aggregation).
**Risk:** Medium — UNION must align all GROUP BY dimensions and preserve
the JsonGroupArray aggregation.

---

### 4. FK intersection queries — 7 sequential filters, each lazy — MEDIUM
**Location:** `query_intersections.py:71–79`

```python
for field in COMIC_FK_FIELDS:   # age_rating, original_format, scan_info, tagger, main_character, main_team, country, language
    fk_intersections[field.name] = self._get_fk_intersection_query(...)
```

7 separate querysets, lazy-evaluated, so 7 queries fire during
serialization. Unlike M2M (UNION-batched), FK intersections are left as
individual querysets.

**Proposed fix:** Merge FK queries into a UNION, partition by model and
materialize as querysets with select / prefetch optimizers.

**Impact:** Medium — 7 queries → 1 UNION + batch fetch.
**Risk:** Medium — UNION with heterogeneous FK models requires field
alignment.

---

### 5. FK intersection extraction — `.first()` on each lazy queryset — MEDIUM
**Location:** `copy_intersections.py:63–65`

```python
@staticmethod
def _copy_fks(obj, fks) -> None:
    for field, fk_qs in fks.items():
        setattr(obj, field, fk_qs.first())   # .first() forces query eval
```

**Impact:** 7 queries (one per FK field).

**Proposed fix:** Materialize all FK querysets in a single batch query,
or pair with the batched UNION from #4.

**Impact:** Medium — 7 queries → 1 batch fetch.
**Risk:** Medium — careful with object construction from batched
results.

---

### 6. Multi-PK aggregate sums — separate query when `len(pks) > 1` — LOW
**Location:** `__init__.py:52–97`

```python
if len(pks) > 1:
    obj = self._aggregate_multi_pk_sums(filtered_qs, obj)
```

Fires a second `.aggregate()` query for SUM(page_count), SUM(size):

```python
sums = self.force_inner_joins(filtered_qs).aggregate(**aggs)
```

**Impact:** 1 additional query when multiple comics are selected.

**Proposed fix:** Include SUM field aggregates in the main queryset from
the start; extract them post-fetch regardless of pk count.

**Impact:** Low.
**Risk:** Low.

---

### 7. Annotation overhead — unused card annotations — LOW
**Location:** `__init__.py:82–86`

Inherits `annotate_card_aggregates()` (card.py:61–83) which includes
`annotate_order_value`, `annotate_group_names`, `annotate_child_count`,
`annotate_bookmarks`, `annotate_progress`, `annotate_order_aggregates`.

Most of these are **excluded** from the metadata serializer output
(metadata.py:58–64). Fields actually used: `mtime` (from `updated_ats`),
`group`.

**Proposed fix:** Refactor `BrowserAnnotateCardView` to have optional
annotation methods, or create a `MetadataAnnotateMinimal` class.

**Impact:** Low — CPU time in annotation building; unlikely to reduce
query count meaningfully.
**Risk:** Low — organizational refactoring.

---

### 8. Comic PK extraction — forced early evaluation — LOW
**Location:** `query_intersections.py:48–53`

```python
def _get_comic_pks(self, filtered_qs: QuerySet) -> frozenset[int]:
    comic_pks = filtered_qs.distinct().values_list(pk_field, flat=True)
    return frozenset(comic_pks)   # forces evaluation
```

Materializes the filtered queryset early. Code comment justifies this:
"Evaluating it now is probably faster than running the filter for every
m2m anyway." Sound design.

**But:** if filtered_qs lacks `select_related` chains, those FKs are lost
after materialization.

**Proposed fix:** Ensure filtered_qs is fully `prefetch_related` before
evaluation. Or use the frozenset as a subquery (Q object) in subsequent
queries.

**Impact:** Low — data-structure optimization, not a query-count
reduction.
**Risk:** Low.

---

### 9. Serializer method fields — potential hidden N+1 — UNKNOWN
**Location:** `serializers/browser/metadata.py` & parent `ComicSerializer`

The MetadataSerializer defines `mtime = SerializerMethodField(read_only=
True)` which chains through `obj.updated_ats` (an annotation). Safe.

**But:** must audit `ComicSerializer` for additional `SerializerMethodField`s
that might trigger lazy FK access.

**Impact:** Unknown — 0–N additional queries.
**Proposed fix:** Audit ComicSerializer and trace all
`SerializerMethodField` implementations.
**Risk:** Medium (depends on parent serializer).

---

## Cross-cutting Observations

### A. Query architecture: deferred intersection batching

The metadata view **intentionally delays FK / M2M intersection queries**
until after the main queryset is annotated, which avoids inflating the
main query with unnecessary joins. **Well designed.**

However, the deferred queries are **not fully batched** — separate
querysets for M2M, FK, and groups, evaluated sequentially. Should
**merge these into 2-3 batch queries total** (main + intersections +
groups).

### B. Annotation strategy: sum vs. distinct-count

`annotate.py` correctly separates `SUM_FIELDS` (direct aggregation) from
intersection fields (need distinct checks). Good — but applies
`_intersection_annotate()` three times instead of once (see #2).

### C. Prefetch optimizer table

`const.py:M2M_QUERY_OPTIMIZERS` defines per-model `select_related`,
`prefetch_related`, `only()` clauses. Applied in
`_get_optimized_m2m_query()`. **Good practice**, but only used after the
11 hydration queries (see #1).

### D. Caching — not exploited

Metadata has HTTP `cache_page(METADATA_TIMEOUT)` (urls/api/browser.py:44).
No in-app caching. Consider a keyed cache per (user, group, pks) with
invalidation on Comic updates. Metadata for a stable group is highly
cacheable.

### E. Lazy queryset materialization

Many querysets are returned as lazy objects (M2M, FK intersections,
groups) and only materialize during serialization. Defers execution but
makes it hard to batch. Explicit eager batching would improve clarity and
performance.

---

## Query count baseline (group='c', single comic)

| Phase | Queries | Breakdown |
|-------|---------|-----------|
| Main queryset + annotations | 1-2 | Main comic query + order/card aggregates |
| Value-field intersections (3 calls) | 6 | 3 distinct-count aggregates + 3 value fetches |
| Group queries | 4 | Publisher, Imprint, Series, Volume |
| M2M UNION + hydrations | 12 | 1 UNION + 11 model refetches |
| FK intersections | 7 | 7 lazy querysets (evaluated on serialization) |
| FK extraction | 7 | 7 × .first() calls |
| **Total** | **~37-40** | |

**After optimizations** (consolidating #1-7):
- Consolidate value-field annotations: -4 queries
- Batch M2M hydrations: -10 queries
- Batch FK intersections: -6 queries
- Batch group queries: -3 queries
- **Total: ~15 queries** (60% reduction)

---

## Out of Scope / Deferred

1. **ComicSerializer audit** — trace all SerializerMethodFields for
   lazy FK access.
2. **Database schema optimization** — denormalize intersection counts?
   Materialized views?
3. **Caching layer** — implement Redis / cachalot-scoped caching for
   metadata.
4. **FTS mode interaction** — verify FTS-specific query paths.
5. **Folder view edge cases** — confirm folder-specific metadata doesn't
   trigger path traversal queries.

---

## Summary

The metadata subsystem has **well-designed deferred batch logic for
intersections**, but **executes them sequentially** (11 M2M hydrations,
7 FK queries, 4 group queries, 3 annotation chains). Consolidating these
into 2-3 batch queries would achieve **~60 % query reduction**.

Highest-impact fixes: M2M hydration batching (#1), FK batching (#5),
value-field annotation consolidation (#2).
