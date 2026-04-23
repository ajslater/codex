# Browser Views Performance Analysis — Meta Plan

## Scope

`codex/views/browser/` is ~4,273 lines across 36 Python files. It implements the
primary read path of the application: listing groups/books, pagination,
annotations (card, bookmark, order), filtering (ACL, bookmark, search, group),
metadata detail views, covers, downloads, and settings. Every browse page in the
UI (and every OPDS feed) hits this subsystem, so it is the highest-value target
for whole-application performance work.

The analysis is too large for a single plan — file-level heuristics ("add
select_related here") miss cross-cutting costs like redundant COUNT queries,
join demotion side effects, and annotation churn between `annotate`/`alias`.
Breaking the directory into logical subsystems lets each plan go deep on the
interactions inside its slice while this meta plan tracks the shared themes.

## Approach

1. Each sub-plan is produced by a focused exploration pass against the real code
   (not this meta plan). Sub-plans identify concrete hotspots, cite file paths +
   line numbers, and propose ranked changes with estimated impact and risk.
2. After all sub-plans land, a final roll-up plan (`99-summary.md`) is written
   that de-duplicates themes, ranks the entire backlog, and sequences the work
   into landing order (independent vs. dependent changes).
3. This meta plan is kept short on purpose. Anything specific to a subsystem
   belongs in that subsystem's file.

## Sub-plans

| #   | File                      | Subsystem                                                                                        | Files covered                                                                                                                                                                                           |
| --- | ------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `01-core-browser-flow.md` | Main view orchestration, pagination, validation, settings, title, order resolution, mtime checks | `browser.py`, `paginate.py`, `page_in_bounds.py`, `validate.py`, `settings.py`, `saved_settings.py`, `breadcrumbs.py`, `params.py`, `title.py`, `order_by.py`, `mtime.py`, `group_mtime.py`, `const.py` |
| 2   | `02-annotations.md`       | Card, order, bookmark annotations                                                                | `annotate/card.py`, `annotate/order.py`, `annotate/bookmark.py`                                                                                                                                         |
| 3   | `03-filters.md`           | ACL, bookmark, group, field filters + search parsing and FTS                                     | `filters/filter.py`, `filters/bookmark.py`, `filters/field.py`, `filters/group.py`, `filters/search/*`                                                                                                  |
| 4   | `04-metadata.md`          | Metadata detail view                                                                             | `metadata/__init__.py`, `metadata/annotate.py`, `metadata/const.py`, `metadata/copy_intersections.py`, `metadata/query_intersections.py`                                                                |
| 5   | `05-auxiliary.md`         | Cover, download, bookmark action views                                                           | `cover.py`, `download.py`, `bookmark.py`                                                                                                                                                                |
| 6   | `06-choices.md`           | Choices / filter-sidebar endpoints                                                               | `choices.py`                                                                                                                                                                                            |

## Shared themes to watch for in every sub-plan

These are the recurring pathologies suspected from the initial scan; each
sub-plan should report on them in its slice rather than re-deriving them:

1. **Redundant COUNT queries.** `browser.py:94`, `paginate.py:64-70`,
   `metadata/__init__.py` — a page often runs a separate filtered COUNT, then
   another COUNT after pagination, then `libraries_exist()` (`browser.py:206`).
   Each is a full round-trip.
2. **`distinct=True` on aggregates and `.distinct()` on querysets.**
   `filters/filter.py:65` forces `DISTINCT` on every filtered queryset; multiple
   `Sum(..., distinct=True)` and `Count(..., distinct=True)` appear in
   `annotate/bookmark.py` and `annotate/order.py`. DISTINCT across many-to-many
   joins is expensive and sometimes correct-but-unnecessary after a proper
   `group_by()`.
3. **Annotation duplication.** `annotate_order_aggregates` is followed by
   `annotate_card_aggregates`, which re-annotates `order_value`, `sort_name`,
   `filename`, bookmarks — often as `alias` then again as `annotate`, or the
   other way around. Every annotation pushed into SELECT adds work.
4. **Subquery-style aggregates on many-to-many relations** (bookmarks,
   story_arc_numbers, folders). `JsonGroupArray("id", distinct=True)` fires on
   every list page (`annotate/order.py:263`) and `JsonGroupArray(updated_at)`
   fires again in card annotations (`annotate/card.py:79-83`). These arrays are
   consumed for mtime/ETag computation — a cheaper scalar may suffice.
5. **Join demotion / forced inner joins.** `force_inner_joins` in
   `filters/filter.py:13-21` is applied late; `group_mtime.py:88` notes it can't
   run on aggregates. Wrong-shape joins make SQLite's planner pick bad indexes.
6. **Search path cost.** FTS5 MATCH and the search parser
   (`filters/search/parse.py`, 266 lines) are on the hot path when search is
   active; `annotate_search_scores` adds `group_by("id")` (a full re-grouping)
   in `annotate/order.py:215`.
7. **`libraries_exist` and similar "global truth" probes** run every request
   (`browser.py:206`). These should be cached or folded into an earlier query.
8. **Breadcrumbs re-walk the group hierarchy** each request (`breadcrumbs.py`,
   176 lines) — worth auditing for N queries up a chain.
9. **Metadata intersections** (`metadata/query_intersections.py`,
   `metadata/copy_intersections.py`) look structurally expensive — one query per
   many-to-many relation set against the group.
10. **Cachalot coverage.** `cachalot` is installed app-wide
    (`settings/__init__.py:271`) but there are no explicit cache
    hints/invalidations in browser views. Cachalot caches by whole-table change
    signal — writes to `Comic` invalidate everything. Worth quantifying vs.
    adding a targeted app-level cache for breadcrumbs / admin flags /
    libraries_exist / choices.

## Deliverable shape

Each sub-plan uses this skeleton so the roll-up can merge them mechanically:

```
# <subsystem>

## Inventory
<one-line-per-file summary of what the file does and rough line count>

## Hotspots
<ranked list, each with: path:line, what it does, why it's slow, proposed
change, estimated impact (High/Med/Low), risk (High/Med/Low)>

## Cross-cutting observations
<patterns that don't localize to one file>

## Out of scope / deferred
<anything noticed but intentionally left for the other sub-plans or a later pass>
```

## Final deliverable

`99-summary.md` — the single markdown document the user asked for. It is the
synthesis across sub-plans: ranked backlog, landing order, and rough effort. The
sub-plan files remain as appendices for anyone who wants the evidence.
