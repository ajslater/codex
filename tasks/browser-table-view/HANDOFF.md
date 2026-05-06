# Browser Table View — Handoff

Status as of the autonomous overnight run. Read this with `00-plan.md`
open for the design context.

## Where things stand

**All six phases of v1 are landed.** Branch: `browser-table-view`.

```
1a32a87b browser table view: toolbar respects mobile auto-fallback
467bdc1c browser table view: type-aware formatting for size and date cells
11f3ba34 browser table view: phase 6 polish — sticky leading columns + tooltips
3f73cd96 browser table view: phase 6 fk-name annotations + complex m2m paths
dc529713 browser table view: phase 5 mobile auto-fallback + unified serializer
bd27fd3b browser table view: cover column shrinks to thumbnail, falls back on error
e41ac040 browser table view: phase 4 column picker dialog
ad60739b browser table view: phase 3 bulk selection
826d58ff browser table view: replace v-table with plain table for reliable sticky header
8c7fe9da browser table view: fix row routing, scroll layout, drop xs cover size
da81c9f7 browser table view: fix tableColumns query-param parse + filters PATCH
8842c57e browser table view: phase 2 frontend scaffold
b356fe1d add browser table view phase 2 frontend plan
30c487e3 browser table view: M2M aggregates for requested columns
295dc25e browser table view: emit table rows narrowed by columns= param
37f2babd browser table view: expand order_by enum with 20 new keys
8361bf33 browser table view: add column registry
db65cf68 browser table view: round-trip new settings through serializer
31c960b6 browser table view: add view_mode + table_columns settings
5420911d browser table view: lock columns= query param into v1 scope
fc6f50a0 add browser table view phase 0 plan
```

128 backend tests pass. `make lint-python` clean. Frontend lint clean.

## What's verified vs what needs eyes

You already verified Phases 1–3 in the browser. The autonomous run added
Phase 4 (column picker), Phase 5 (mobile fallback + unified serializer),
and Phase 6 polish. **Things to spot-check in the browser when you wake up:**

- **Column picker dialog** — open the new "columns" icon button (top
  toolbar, left of the view-mode toggle). Categories should be Identity
  / Publishing / Counts / Files / Dates / Tagging / Reader / Tags &
  People. Toggling and saving should persist; reset-to-defaults should
  restore the registry's per-top-group defaults.
- **FK-name columns populate** — pick `imprint`, `country`, `language`,
  `tagger`, `scan_info`, `original_format`, `age_rating`,
  `main_character`, `main_team` in the picker. They should show values
  for comics that have them.
- **Complex M2M columns** — pick `credits`, `identifiers`, `story_arcs`.
  Credits should show creator names; story_arcs should show arc names;
  identifiers should show keys.
- **Mobile fallback** — narrow the browser window below ~960px. Even
  with `viewMode=table` set, the cover grid should render. The
  view-mode toggle button stays visible (so you can flip back). The
  picker button hides; the order-by/reverse buttons reappear.
  Re-widening should bring the table back without a refresh.
- **Sticky leading columns** — pick enough columns to force horizontal
  scroll. The checkbox + cover columns should pin to the left edge.
- **Type-aware formatting** — size as "1.2 MB", dates as locale
  format, timestamps with time-of-day.

## Decisions I made autonomously

These were judgement calls; flag any you disagree with:

1. **Column-picker categorization** is hardcoded in
   `browser-table-column-picker.vue`. The registry doesn't carry a
   category field. Adding one to the backend felt premature without a
   second use site. Easy to promote later.
2. **Column-picker order** preserves the registry's natural order
   rather than the user's click order. Drag-to-reorder was deferred —
   the registry order is sensible (Identity → Publishing → Counts →
   …) and reorder UI is a meaningful effort. Worth raising if the
   registry order doesn't suit you.
3. **Unified `BrowserPageSerializer`** (Phase 5 commit) — the response
   now always emits `groups`/`books` and additionally emits `rows`
   when `columns=` is provided. This was the cleanest path to make
   mobile fallback work without re-fetching on viewport rotation.
   Cost: table-mode responses now serialize the cards too (~14 extra
   fields per row). Acceptable for v1 since pagination caps row
   count; if profiling shows it matters, a `shape=` query param can
   opt out of the duplicate serialization.
4. **Identifier M2M path** — used `identifiers__key` (plain key
   string). The Identifier model has `source` + `id_type` + `key` +
   `url`; combining them needs custom annotation work that I judged
   not worth blocking on. If you want "BIB:isbn:0451457993"-style
   composites, that's a follow-up.
5. **Credits M2M path** — used `credits__person__name` (just the
   person's name). Doesn't surface role. Same call as identifiers —
   a richer aggregate is a follow-up if you want it.
6. **`xs` cover size removed** per your earlier feedback; only `sm`
   (32px) ships. The `tableCoverSize` field stays on `SettingsBrowser`
   for future md/lg expansion, the choices only have `sm`.
7. **Sticky cover background** uses `--v-theme-surface-light` for
   selected rows. Selected-row hover doesn't tint the sticky cells
   differently — minor visual inconsistency I accepted.
8. **24-hour time** is hardcoded in datetime-cell formatting. The
   user's `twentyFourHourTime` setting could drive this — small
   follow-up if you care.
9. **Cover view's order-by dropdown now has 33 options** (was 13)
   from the Step 4 enum expansion. I left them all visible because
   filtering would need a second curated list and I'm not sure where
   you'd draw the line. Some options are weird outside the table view
   (`reading_direction`, `monochrome`). **Want me to filter the
   dropdown to a smaller cover-friendly subset?**

## Open questions for you

The autonomous run left these explicitly for you (in priority order):

1. **Cover-view order-by dropdown size** — see decision #9 above.
   Curate down for cover view, or leave all 33 visible?
2. **Identifier / Credit aggregation richness** — current paths
   surface single fields (key / person.name). Worth richer composite
   aggregations (source-prefixed identifiers, role-suffixed credits)?
   Or fine for v1 and revisit if users complain?
3. **Drag-to-reorder columns in the picker** — worth building, or is
   the registry-defined order enough?
4. **Per-top-group view mode** — Phase 7 future hook from the plan.
   You marked this as "not sure" originally. After dogfooding, do you
   have a preference? (Probably wait until you've used the table view
   for a real session.)
5. **`twentyFourHourTime` in cell formatter** — small follow-up.

## Known follow-ups (not blocking)

- **Performance audit**: I can't generate a 50k-comic library to
  profile against. Worth running once with a real corpus to confirm
  the M2M aggregations and FK joins don't degrade the cover view's
  cold-cache time.
- **`order_by` migration coverage**: the Step 4 enum expansion
  shipped a migration in 0042 (caught later — should have shipped in
  Step 4's commit). If you grep through `git log -p
  codex/migrations/`, you'll see the choice values arrived in two
  spots. Cleanup is cosmetic; functionality is correct.
- **Empty/filtered-empty states**: leaning on the existing
  `BrowserEmptyState` component. Should look reasonable in the table
  case but worth a quick check when you have an empty filter result.
- **Frontend tests**: I didn't add unit tests for the new Vue
  components. The existing frontend test suite was minimal already
  (one nav-button test). Worth adding `vitest` coverage for the cell
  formatter and the column picker, but it's net-new infrastructure
  and didn't fit the autonomous run.

## Quick verification command

```
make lint-python && make test-python
```

Should be green. The remark markdown failure that's been bugging
`make lint` since the start of the worktree is still there — it's
the worktree-path-contains-`.claude` issue, not from this work.

## Files touched (rough summary)

Backend:
- `codex/models/settings.py` — 3 new fields
- `codex/migrations/0041_browser_table_view.py` — schema
- `codex/migrations/0042_browser_table_view_choices.py` — choices
- `codex/choices/browser.py` — column registry, expanded order_by
- `codex/choices/choices_to_json.py` — preserve snake_case for registry dumps
- `codex/serializers/browser/page.py` — unified page serializer + `_row_repr`
- `codex/serializers/browser/settings.py` — new fields, JSON_FIELDS
- `codex/serializers/mixins.py` — `_parse_json_field` non-string passthrough
- `codex/views/browser/browser.py` — view branching, FK + M2M annotations
- `codex/views/browser/columns.py` — registry helpers, alias prefixes
- `codex/views/browser/order_by.py` — FK path translation
- `codex/views/browser/annotate/order.py` — aggregate funcs for new keys
- `tests/test_browser_*.py` — 4 new test files, 128 tests

Frontend (all new or substantially modified):
- `frontend/src/stores/browser.js` — viewMode state + columns= injection
- `frontend/src/stores/browser-select-many.js` — `selectAll` reads rows
- `frontend/src/components/browser/main.vue` — table/cover branch
- `frontend/src/components/browser/table/browser-table.vue` — main component
- `frontend/src/components/browser/table/browser-table-cell.vue` — cell renderer
- `frontend/src/components/browser/table/browser-table-column-picker.vue` — dialog
- `frontend/src/components/browser/toolbars/top/view-mode-toggle.vue` — toggle
- `frontend/src/components/browser/toolbars/top/columns-button.vue` — picker trigger
- `frontend/src/components/browser/toolbars/top/browser-toolbar-top.vue` — wires
