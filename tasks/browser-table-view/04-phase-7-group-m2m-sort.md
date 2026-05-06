# Phase 7 follow-up: Group-Row M2M Sort + Display

**Status: planning — needs sign-off before implementation.**

The previous M2M-sort experiment landed for Comic rows. Group rows
(Publisher / Series / Volume / Imprint / Folder / Story Arc) currently
fall back to ``sort_name`` when an M2M sort is selected, and M2M cells
on group rows display empty. This experiment fills both gaps.

## What semantic to use

Table view's group rows show one row per group. The M2M cell needs a
single value (or a list of strings) per row. Two natural choices:

### Union — "what M2M values appear *anywhere* in the group's comics"
For a Series row, ``genres`` would list every genre carried by any
comic in the series. Display: rich; sort: groups with the same
"underlying tag set" cluster.

### Intersection — "what M2M values appear in *every* comic of the group"
What the metadata-dialog intersection code does today
(``MetadataQueryIntersectionsView._get_m2m_intersection_query``).
Display: shows the group's "core" tags. Sort: empty intersections
collapse all such groups into one bucket regardless of how
distinct their actual sets are.

I recommend **union** for the table-view experiment. Rationale:

- The metadata view's intersection answers a different question (what's
  shared) for a different surface (the dialog). The table cell
  answers "what's in this group", and the sort follows the cell.
- Union is much cheaper to compute — one aggregate per row, exactly
  the same shape as the Comic-level case but with a longer relation
  chain via ``rel_prefix`` (which already exists).
- The user's comic browse with a Series selected today shows all
  the genres across its comics, not just shared ones. Matching that
  expectation in table view is more intuitive.

If you want **intersection** instead, the metadata code is reusable —
``_get_m2m_intersection_query`` operates on a comic-pks set per
field. We'd need to call it per visible group row (or batch via a
union-of-through-table queries) and stash the result on the row. Cost
scales with `(rows on page) × (M2M columns visible)` queries; can
batch into one union-all query similar to ``_query_m2m_intersections``.
Doable if you want it, but more code and slower; flag it and I'll
implement that variant instead.

## Reuse of metadata-view code

For **union**: there's no direct code reuse. The metadata view is
about intersections; we use the same primitives (JsonGroupArray, the
existing M2M path map) but with a relation prefix.

For **intersection** (alternative): direct reuse of
``_get_m2m_intersection_query`` and the through-table union pattern in
``_query_m2m_intersections``. The metadata view returns model
querysets; we'd consume the related_id list and convert to names.

In general the table-view code already reuses the same M2M path map,
column registry, and JsonGroupArray helpers — those are the cross-
cutting pieces. The metadata-intersection logic is specifically about
the dialog's "what's shared" question.

## Implementation (union variant)

### Backend

1. **Group M2M paths.** Mirror ``_M2M_COLUMN_PATHS`` with a per-group
   variant prefixed via ``rel_prefix``. Most paths are simple
   string concatenations; the composite ``credits`` and
   ``identifiers`` Case expressions take a relation prefix as
   well — refactor those into helpers that accept a prefix:
   ```python
   def _credit_expr(rel="credits__"):
       return Case(
           When(**{f"{rel}role__isnull": True}, then=F(f"{rel}person__name")),
           default=Concat(...),
           output_field=CharField(),
       )
   ```
   Same for identifiers.

2. **A second annotations helper.** ``m2m_annotations_for_groups(columns, rel_prefix)``
   that returns ``{alias: JsonGroupArray(prefixed_path, ...)}``,
   filtered for nulls and ordered alphabetically (intra-row).
   Calls the same ``m2m_alias_for`` so ``_row_repr`` reads via the
   same alias.

3. **Wire into the group queryset path.** In
   ``BrowserView._add_table_view_annotations``, branch on
   ``qs.model is Comic`` (existing) vs. group: for groups, call
   the new ``m2m_annotations_for_groups`` with the appropriate
   ``rel_prefix``.

4. **Update ``annotate_order_value``.** Currently group + M2M sort
   falls back to sort_name. Change to use the group M2M alias
   (now that groups carry the annotation):
   ```python
   elif qs.model is not Comic and is_m2m_sort:
       order_value = F(m2m_alias_for(self.order_key))
   ```
   Comic case unchanged.

5. **Update ``add_order_by`` for groups.** Currently the non-Comic /
   non-Volume path uses ``order_value``. That stays — the
   ``order_value`` annotation now carries the M2M alias for sort.

### Frontend

No changes. The column registry already declares M2M columns
sortable; group rows just start producing data and sort correctly.

### Display

Same alias drives both display and sort. ``_row_repr`` already
reads M2M from the alias for Comic rows; the same path works for
group rows once they carry the annotation.

## Performance

Cost per page:

- **Display annotation** (already per visible M2M column): a
  ``JsonGroupArray`` aggregate over `rel_prefix.m2m_field__name`,
  one per row × one per visible M2M column. The relation chain is
  longer than Comic's (Series → comic → genres), so the underlying
  join graph is heavier.
- **Sort**: same aggregate, same cost — just used in ORDER BY.

For a Series page with 30 rows and one visible M2M column,
that's 30 grouped aggregates. Should be well under 100ms on an
indexed database. Profile-and-confirm before considering the
intersection variant.

If profiling shows it's too slow:

1. Drop to a simpler "first M2M element" sort (fast, less useful).
2. Limit M2M annotations to only the column being sorted, not
   every visible M2M column.
3. Swap to intersection (the *metadata-view-code-reuse* variant)
   which has a fixed per-page cost regardless of row count.

## Correctness

- **Empty groups**: a Series with comics but none with genres
  produces ``[]`` (the null filter excludes the LEFT JOIN nulls,
  consistent with the Comic case).
- **No comics**: a brand-new Series with zero comics has no
  through-table rows and produces ``[]``. Sort places empties
  together — same equivalence-class behavior as Comic case.
- **Volume sort_name fallback**: previously needed because Volume
  doesn't have a real ``sort_name`` field. Now that we sort on the
  M2M alias for groups, we don't need the sort_name workaround in
  the M2M path — it stays for the existing non-M2M paths.
- **StoryArc**: the relation chain is ``storyarcnumber__comic__``,
  longer than other groups. ``rel_prefix`` already returns this for
  StoryArc, so the annotations should work — verify in tests.

## Tests

- Two Series with the same union of child genres ⇒ adjacent in
  sorted output.
- A Series with no genre-bearing comics ⇒ `[]` in the cell, sorts
  with the empty equivalence class.
- StoryArc + M2M sort works end-to-end (the longer relation
  chain).
- Display test: M2M cell on a Series row populates with the
  child-aggregated values.

## Out of scope

- Intersection variant — implementable on demand, deferred unless
  you prefer it.
- Per-row count-based sort and per-row first-element sort — the
  fallback ladder if union proves too slow.

---

## Sign-off needed

- **Semantic**: union (recommended) or intersection?
- **If union**: any concerns with the rel_prefix approach for
  StoryArc's longer chain?
- **If intersection**: confirm you want me to wire the per-row
  intersection path, accepting the higher per-page cost?
