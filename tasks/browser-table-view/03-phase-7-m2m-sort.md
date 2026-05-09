# Phase 7 Experiment — M2M Column Sorting

Make M2M columns (genres, tags, characters, credits, identifiers,
locations, series_groups, stories, story_arcs, teams, universes)
sortable in the table view.

This was on the Phase 7 list ("M2M-field sorting — experiment with
sortable genres / tags / characters / credits columns. Likely
strategies: sort by the first M2M element's name, sort by the
joined string aggregate, sort by count.").

## Approach

Sort by the **aggregated JSON-array string**, with intra-array
elements alphabetized. This gives the property the user actually
cares about: comics with the same M2M set sort next to each other,
and empty cells group together. The exact alphabetic order *between*
distinct sets is a side-effect, not the goal.

Concretely: for each row, the aggregated value is a JSON array of
strings sorted alphabetically (e.g. `["Action", "Drama"]`). Two rows
with the same set produce the same JSON literal. ORDER BY on that
literal sorts identical rows together. Empty cells produce `[]`,
which sorts at the start (or end with order_reverse).

## Scope

- **Comic rows**: full M2M sort, via `ORDER BY annotation_alias`.
- **Group rows** (Publisher / Series / Volume / Imprint / Folder /
  Story Arc): fall back to ``sort_name`` when an M2M sort key is
  active. Aggregating M2M across all child comics for sort
  purposes is doubly expensive and the UX value is much smaller —
  group rows already cluster their content. Same fallback pattern
  ``child_count`` already uses for Comic queries.
- **Mode**: only when ``view_mode == "table"``. Cover view doesn't
  expose these keys (the cover-friendly subset already filters them
  out).

## Implementation

### Backend

1. **Sort the intra-row aggregate.** Update ``m2m_annotations_for``
   to pass ``order_by=path`` to ``JsonGroupArray`` so each row's
   array is alphabetized:
   ```python
   JsonGroupArray(path, distinct=True, order_by=path, **kwargs)
   ```
   For composite expressions (`credits`, `identifiers`),
   ``order_by`` accepts the same expression — sorts by the rendered
   composite string.

2. **Expand the order_by enum.** Add the 11 M2M keys to
   ``BROWSER_ORDER_BY_CHOICES``. Same names as the column keys so the
   header-click sort logic works without additional mapping.

3. **Flip the registry's ``sort_key``.** M2M registry entries get
   ``sort_key`` set to their column key. The sortability test
   (``test_registry_sortable_columns_resolve_to_enum``) keeps the
   registry / enum in sync.

4. **Wire Comic ordering.** Update ``_add_comic_order_by`` so that
   when the order key is an M2M key, the head order field becomes
   the alias from ``m2m_alias_for(key)``. The annotation must be on
   the queryset before ``add_order_by`` runs — already true for
   table-view requests via the existing wiring in
   ``_get_group_and_books``.

5. **Fall back for groups.** ``annotate_order_value`` and the group
   path in ``add_order_by`` short-circuit M2M keys to the sort_name
   path. This is the same shape used today for ``child_count`` on
   Comic.

6. **Cover view filtering.** Don't add the M2M keys to
   ``BROWSER_COVER_ORDER_BY_KEYS`` — the cover dropdown stays
   curated to its current 13.

### Frontend

No changes. The column registry drives sortability via ``sort_key``,
so flipping the M2M entries in the registry is enough; clicking an
M2M column header in the table will Just Work via the existing
``onHeaderClick`` path. The cover dropdown stays unaffected because
``BROWSER_COVER_ORDER_BY_KEYS`` doesn't include them.

## Performance

The cost we're adding:

- **Aggregate** (already paid in v1 for M2M-displayed columns): a
  GROUP_CONCAT-equivalent over the M2M relation. SQLite with FK
  indexes is fast at this for per-row aggregation; the table-view
  page size (typically 100 rows) caps the work.
- **Intra-row order_by**: SQLite has to sort within each
  GROUP_ARRAY. This is per-row, log-linear in element count.
  Negligible for typical M2M cardinality (genres: ~3, tags: ~5).
- **Outer ORDER BY on the JSON string**: lexicographic sort on the
  produced array text. SQLite uses binary collation by default; the
  text is short. Negligible relative to the aggregate cost.

Net: a small constant-factor on top of the existing M2M annotation
cost. No new joins. No nested aggregation.

If profiling on a real library shows this is too slow, fallback
strategies in priority order:

1. Sort by **count of distinct values** instead of the joined
   string — a cheaper aggregate (`Count(rel, distinct=True)`),
   loses set-equality grouping but groups by count.
2. Sort by the **first** alphabetical value only (`Min(rel)`).
3. Skip M2M sort entirely on libraries above some threshold and
   warn the user.

## Correctness

- **Null / empty cells**: a comic with no genres produces ``"[]"``
  from JSON_GROUP_ARRAY (the JSON empty-array literal). All such
  rows sort to a single equivalence class — exactly what the user
  asked for.
- **Filtered aggregates**: `credits` and `identifiers` use the
  ``filter=`` Q expression to skip placeholder rows. The filter
  applies before order_by, so the alphabetized array contains only
  meaningful entries.
- **Case sensitivity**: default SQLite ORDER BY is byte-comparison.
  For the *intra-row* sort this matters: "Drama" < "action"
  byte-wise, "Action" < "Drama" alphabetically. The values come
  from related models that use ``db_collation="nocase"`` on their
  ``name`` field, so nocase comparisons should already be the
  default. Verified by the existing `sort_name` sort behavior.
- **Order stability**: JsonGroupArray with ``distinct=True`` plus
  ``order_by=expr`` produces deterministic output. Identical input
  rows yield identical aggregates.
- **Composite columns**: `credits` aggregates as `"Person (Role)"`
  strings; `identifiers` as `"source:type:key"`. Sort is on the
  rendered composite, which is fine for grouping equivalence.

## Tests

- Two comics with identical genre sets ⇒ aggregated arrays sort
  identically (place them adjacent).
- Comic with no genres ⇒ sorts before any comic with genres
  (ascending) or after all (descending).
- Comic with `["Action", "Drama"]` and another with
  `["action", "drama"]` ⇒ sort to the same equivalence class
  (case-insensitive collation on the underlying name fields).
- Sorting groups by an M2M key falls back to sort_name (parity test).

## Open question for sign-off

**Default direction**: M2M columns currently aren't in
``REVERSE_BY_DEFAULT`` (the set of sort keys that the cover-view
dropdown auto-reverses on selection — keys like
`bookmark_updated_at`, `created_at`, `size`). For table-view header
clicks the existing logic is "click new key → ascending; click
active key → toggle direction" — no auto-reverse. I'll keep that
behavior for M2M; flag if you want a default direction.

## Out of scope (for this experiment)

- Group-row M2M sort (deferred to a future iteration if needed).
- Sort-by-count and sort-by-first-element strategies (only
  considered if alphabetic-on-aggregate proves too slow).
- A frontend-side label that signals "this column sorts by group
  equivalence, not strict alphabetical" — possibly a tooltip on
  the header.
