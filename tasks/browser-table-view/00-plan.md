# Browser Table View — Plan

## Goal

A second browser presentation that complements the cover-emphasized
view: comics shown as rows in a sortable table with user-selectable
metadata columns, a leftmost checkbox column for bulk selection, and a
dialog for adding/removing columns from the visible set. Filters,
choices, top-group selection, and search continue to work exactly as
they do in cover view. The order-by dropdown and reverse toggle are
*replaced by* clicking on column headers within the table view, but
remain in the cover view.

This is not a replacement for cover view. It is an alternate
presentation chosen per-user, persisted across sessions.

The plan also expands the set of supported `order_by` values for the
browser settings *in general* (cover view's dropdown gets new options;
table view exposes them as sortable columns), since the table view's
header-click model demands a much wider sortable surface.

A future phase may allow inline cell editing to write tags directly to
comics. v1 must not paint that into a corner.

OPDS is unrelated and out of scope — it's a separate feed format with
its own serializers, and there's no user-facing reason to bring the
table model into it.

## Decisions

Recorded from the Phase 0 alignment pass. Open items are tracked at
the bottom under "Remaining open questions".

- **View-mode persistence** — `view_mode` field on `SettingsBrowser`,
  not a URL param. Single global scalar for v1; per-top-group
  promotion is tracked as a Phase 7 future hook.
- **Column visibility scope** — persisted per top-group (JSON map
  keyed by `p|i|s|v|c|f|a`).
- **Sort model** — single-column for v1. Multi-column deferred.
- **M2M columns** — display-only; not sortable in v1. M2M sorting is
  flagged as a future experiment in Phase 7; cost is the open
  question.
- **API shape** — table view requests pass a `columns=` query param;
  backend narrows annotations / aggregates to the requested column
  set. Cover view stays unchanged (returns its existing fixed card
  shape). Decided to do this upfront in v1 since the M2M aggregation
  code is net-new either way and the narrowed version is roughly the
  same effort as always-on. Eliminates what Phase 0 originally tracked
  as Phase 7 optimization debt.
- **Default column sets per top-group** — per the proposal in
  "Architecture proposal → Column visibility persisted per top-group"
  below.
- **Mobile fallback** — auto-switch to cover view under ~768px; user's
  `view_mode` setting is preserved across the fallback.
- **Cover column** — present and sticky after the checkbox, with a
  cover-size control offering at least one option significantly
  smaller than the cover-view thumbnail. See "Frontend components"
  below for the cell shape.
- **`order_by` enum expansion** — ship the proposed 17-key batch as-is.
- **Column picker UX** — modal dialog opened from a "Columns" button
  in the table header.

## Existing browser machinery (recap, with file pointers)

### Backend

- URL: `/api/v3/<group>/<int_list:pks>/<int:page>` →
  [`BrowserView`](codex/views/browser/browser.py:57). Inheritance
  chain bakes in validation, params, ordering, filtering, and model
  resolution.
- Group chars: `r` (root, dispatches by `top_group`), `p i s v c f a`.
  Map at [views/const.py:43](codex/views/const.py:43).
- Top-group choices defined at
  [`BROWSER_TOP_GROUP_CHOICES`](codex/choices/browser.py:42).
- Order-by choices defined at
  [`BROWSER_ORDER_BY_CHOICES`](codex/choices/browser.py:17) — currently
  13 values.
- Order-by application:
  [`BrowserOrderByView.add_order_by`](codex/views/browser/order_by.py:58).
  Stable secondary sort on `pk` is already appended.
- Filter keys list at
  [`BROWSER_FILTER_KEYS`](codex/views/browser/const.py) (~24 fields,
  mostly M2M like genres, characters, tags, identifiers).
- Choices endpoints `/choices_available` + `/choices/<field>` already
  cover the full filter surface — table view reuses them unchanged.
- Settings persistence:
  [`SettingsBrowser`](codex/models/settings.py:318) (per-user *and*
  per-session, session takes precedence). Holds `top_group`,
  `order_by`, `order_reverse`, `search`, `custom_covers`,
  `dynamic_covers`, time/filename flags. FK to
  [`SettingsBrowserShow`](codex/models/settings.py) (p/i/s/v
  visibility) and OneToOne to
  [`SettingsBrowserFilters`](codex/models/settings.py:194) +
  [`SettingsBrowserLastRoute`](codex/models/settings.py).
- Per-page response serializer:
  [`BrowserPageSerializer`](codex/serializers/browser/page.py:74).
  Cards via
  [`BrowserCardSerializer`](codex/serializers/browser/page.py:20) —
  ~14 fields, optimized for the cover grid.

### Frontend

- Top-level: [`browser.vue`](frontend/src/browser.vue). Composes
  `BrowserHeader` (toolbars) + `BrowserMain` (card grid) +
  `BrowserNavToolbar` (paging) + `BrowserSettingsDrawer`.
- Top toolbar:
  [`browser-toolbar-top.vue`](frontend/src/components/browser/toolbars/top/browser-toolbar-top.vue)
  hosts `top-group-select`, `order-by-select`, `order-reverse-button`,
  `filter-by-select`, search.
- Pinia: [`stores/browser.js`](frontend/src/stores/browser.js) — state
  shape, `setSettings()`, `loadBrowserPage()`, `loadSettings()`,
  filter-choice loading.
- Bulk selection already exists for cover view:
  [`stores/browser-select-many.js`](frontend/src/stores/browser-select-many.js).
  Toolbar:
  [`browser-toolbar-select-many.vue`](frontend/src/components/browser/toolbars/select-many/browser-toolbar-select-many.vue).
  Bulk-ops API: `updateGroupBookmarks({group, ids: pks}, ...)`.
- Vuetify table precedent: only one usage of `v-data-table-virtual` in
  [`admin-table.vue`](frontend/src/components/admin/tabs/admin-table.vue)
  — bare wrapper, not strong precedent. Greenfield is fine.
- View-mode toggle precedent: none. The `top_group` setting is the
  closest analogue — a setting that materially changes what gets
  rendered.

## Architecture proposal

### View mode is a setting on `SettingsBrowser`

Add `view_mode: "cover" | "table"` to
[`SettingsBrowser`](codex/models/settings.py:318), default `"cover"`. A
toggle button in the top toolbar flips it; persisted via the existing
`setSettings()` flow. The URL `/:group/:pks/:page` does not change.

Rationale: matches the existing `top_group` precedent. URLs are
already long. Settings persist server-side as a matter of course.

### Column visibility persisted per top-group

Different top-groups care about different columns. Comic rows want
`issue_number` and `volume_name`; publisher rows don't. Persist as a
JSON map keyed by top-group:

```json
{
  "p": ["cover", "name", "child_count"],
  "i": ["cover", "name", "publisher_name", "child_count"],
  "s": ["cover", "name", "publisher_name", "year_range", "issue_count"],
  "v": ["cover", "name", "series_name", "year", "issue_count"],
  "c": ["cover", "name", "issue_number", "series_name", "volume_name",
        "year", "page_count", "size"],
  "f": ["cover", "name", "child_count"],
  "a": ["cover", "name", "publisher_name", "child_count"]
}
```

Stored on `SettingsBrowser` as a single JSONField; backend supplies
defaults; `null` per-group means "use defaults for that top-group".

### Header-click sorting reuses `order_by` / `order_reverse`

Click a sortable column header → patch `order_by` to that column. Click
the active column again → toggle `order_reverse`. The same
`order_by`/`order_reverse` settings used by cover view are reused; the
table view simply doesn't render the dropdown / button — it renders
sort arrows in headers instead.

Single-column sort for v1. Multi-column (shift-click for secondary)
left for a future iteration.

Implication: every sortable visible column maps to a real `order_by`
key. Non-sortable columns (M2M list aggregates like `genres`,
`characters`) render no sort affordance and reject clicks.

### Expanded `order_by` enum

Today's [`BROWSER_ORDER_BY_CHOICES`](codex/choices/browser.py:17) has
13 entries. Proposed additions for v1:

| Key                  | Comic field              | Notes                          |
|----------------------|--------------------------|--------------------------------|
| `series_name`        | `series__name`           |                                |
| `volume_name`        | `volume__name`           | Combined with `volume__number_to` for ranges |
| `publisher_name`     | `publisher__name`        |                                |
| `imprint_name`       | `imprint__name`          |                                |
| `country`            | `country__name`          | FK                             |
| `language`           | `language__name`         | FK                             |
| `original_format`    | `original_format__name`  | FK                             |
| `tagger`             | `tagger__name`           | FK                             |
| `scan_info`          | `scan_info__name`        | FK                             |
| `reading_direction`  | `reading_direction`      | enum                           |
| `monochrome`         | `monochrome`             | bool                           |
| `year`               | `year`                   |                                |
| `month`              | `month`                  | sorts within year              |
| `day`                | `day`                    |                                |
| `metadata_mtime`     | `metadata_mtime`         |                                |
| `main_character`     | `main_character__name`   | FK                             |
| `main_team`          | `main_team__name`        | FK                             |

Each addition needs:

1. Entry in `BROWSER_ORDER_BY_CHOICES`.
2. Branch in
   [`BrowserOrderByView._add_comic_order_by`](codex/views/browser/order_by.py:30)
   for any field needing a composite head (most can fall through
   the default single-field path).
3. Validation in
   [`BrowserSettingsSerializer`](codex/serializers/browser/settings.py).
4. UI label + group affinity (which top-groups expose this column).

M2M fields (`genres`, `characters`, `tags`, `teams`, `locations`,
`stories`, `story_arcs`, `series_groups`, `universes`, `identifiers`,
`credits`) are *not* added to `order_by`. They become display-only
columns.

### API shape — `columns=` query param narrows annotations

Reuse `/api/v3/<group>/<pks>/<page>`. Table-view requests carry a
`columns=` query param listing the column keys the frontend wants. The
backend builds the queryset annotations dynamically from that set:
scalar/FK joins are added only when their column is requested, and
M2M aggregates (`JsonGroupArray` / `GroupConcat`) are added only for
the requested M2M columns.

A new `BrowserTableRowSerializer` returns rows with only the requested
fields (plus `pk`, which is always emitted as the row identity). Cover
view requests stay unchanged — they return the existing fixed
`BrowserCardSerializer` shape with no `columns=` param involved.

The column registry (defined below) carries the metadata needed to
drive this narrowing — `field` (ORM path), `m2m` (annotation strategy),
`sortable` (validation against `order_by`).

Validation: every entry in `columns=` must be a registry key. Sorting
by a column not in the requested set is allowed (cover view's order-by
dropdown surfaces the full enum), but in table-view UI the user can
only click visible headers, so this never collides in practice.

### Column registry — single source of truth

A registry shared between backend and frontend. Backend owns the
canonical list (column key → comic field path, sortability, M2M,
default top-groups, label). Frontend pulls it at app load.

```python
# codex/views/browser/columns.py
TABLE_COLUMNS = MappingProxyType({
    "cover":         {"label": "Cover",          "field": None,                "sortable": False, "m2m": False, "default_top_groups": {"p","i","s","v","c","f","a"}},
    "name":          {"label": "Name",           "field": "sort_name",         "sortable": True,  "m2m": False, "default_top_groups": {"p","i","s","v","c","f","a"}},
    "issue_number":  {"label": "Issue",          "field": "issue_number",      "sortable": True,  "m2m": False, "default_top_groups": {"c"}},
    "series_name":   {"label": "Series",         "field": "series__name",      "sortable": True,  "m2m": False, "default_top_groups": {"v","c"}},
    "volume_name":   {"label": "Volume",         "field": "volume__name",      "sortable": True,  "m2m": False, "default_top_groups": {"c"}},
    "publisher_name":{"label": "Publisher",      "field": "publisher__name",   "sortable": True,  "m2m": False, "default_top_groups": {"i","s","a"}},
    "page_count":    {"label": "Pages",          "field": "page_count",        "sortable": True,  "m2m": False, "default_top_groups": {"c"}},
    "size":          {"label": "Size",           "field": "size",              "sortable": True,  "m2m": False, "default_top_groups": {"c"}},
    "year":          {"label": "Year",           "field": "year",              "sortable": True,  "m2m": False, "default_top_groups": {"v","c"}},
    "child_count":   {"label": "Count",          "field": "child_count",       "sortable": True,  "m2m": False, "default_top_groups": {"p","i","s","f","a"}},
    "issue_count":   {"label": "Issues",         "field": "issue_count",       "sortable": True,  "m2m": False, "default_top_groups": {"s","v"}},
    # ... + every additional sortable field
    "genres":        {"label": "Genres",         "field": "genres",            "sortable": False, "m2m": True,  "default_top_groups": set()},
    "tags":          {"label": "Tags",           "field": "tags",              "sortable": False, "m2m": True,  "default_top_groups": set()},
    "characters":    {"label": "Characters",     "field": "characters",        "sortable": False, "m2m": True,  "default_top_groups": set()},
    # ... + remaining M2M fields
})
```

Each entry future-extensible for inline editing:

```python
"editable":     False,        # v1
"edit_widget":  "decimal",    # v2 hint
```

Exposed to the frontend through a new key on the settings response (or
a dedicated `/api/v3/r/columns` endpoint — either works; lower-friction
to bolt onto the existing settings response).

### Frontend components

```
frontend/src/components/browser/table/
  browser-table.vue            # top-level: <v-data-table-server> wrapper
  browser-table-row.vue        # row: checkbox + cells, click → reader
  browser-table-cell.vue       # cell value renderer (component-per-type)
  browser-table-cells/
    cell-cover.vue             # thumbnail; size prop (xs/sm/md)
    cell-text.vue              # plain string
    cell-decimal.vue           # issue_number, etc.
    cell-size.vue              # human-readable bytes
    cell-date.vue
    cell-list.vue              # comma-joined M2M with truncate + tooltip
    cell-bool.vue
  browser-table-header.vue     # sortable header w/ arrows
  browser-table-column-picker.vue  # modal dialog
```

**Cover cell sizing**. `cell-cover.vue` accepts a `size` prop. v1
ships at least two sizes:

- `sm` — ~32px tall, the default for table view.
- `xs` — ~16-20px tall, an explicit "much smaller than the normal
  cover" option that keeps row height tight on dense layouts.

The size selector lives in the column-picker dialog (a small radio
group next to the Cover column row), persisted as a sibling field
to the per-top-group columns map. Default is `sm`. Adding `md` later
is trivial; v1 keeps the option list minimal.

`BrowserMain` becomes a switch:

```vue
<browser-card-grid v-if="settings.viewMode === 'cover'" />
<browser-table     v-else />
```

Order-by + reverse controls in `BrowserTopToolbar` are hidden when
`viewMode === 'table'` — the table headers own that affordance. The
view-mode toggle is a single icon button (e.g. `mdi-view-grid` ↔
`mdi-table`) added next to the existing settings button.

### Bulk-selection reuse

[`useBrowserSelectManyStore`](frontend/src/stores/browser-select-many.js)
is already wired for cover view. The table row checkbox calls the same
`toggle(item)` action; the existing select-many toolbar
([`browser-toolbar-select-many.vue`](frontend/src/components/browser/toolbars/select-many/browser-toolbar-select-many.vue))
appears unchanged. Header checkbox = select-all-on-page (toggles every
visible row). No backend changes required.

### Mobile

`v-data-table` on a 360px viewport is unusable. Two options:

- **Auto-fallback** (preferred): below ~768px viewport, auto-render
  cover view regardless of `view_mode`. The setting is preserved; the
  table reappears when the viewport widens.
- **Stacked rows**: Vuetify's mobile mode collapses each row into a
  vertical card. Deferred — not a v1 priority.

## Phased implementation

### Phase 0 — Alignment (this doc) — DONE

Decide the open questions below before any code lands.

### Phase 1 — Backend foundations — DONE

- [x] Migration: add `view_mode` to `SettingsBrowser`
- [x] Migration: add `table_columns` JSONField to `SettingsBrowser`
- [x] `codex/views/browser/columns.py` — column registry + defaults
- [x] Expand `BROWSER_ORDER_BY_CHOICES` with new keys
- [x] Update `BrowserOrderByView.add_order_by` for FK-name keys
- [x] Update `BrowserSettingsSerializer` validation (view_mode, columns, order_by)
- [x] `BrowserTableRowSerializer` + lazy annotations for M2M aggregates
- [x] Expose column registry through settings response
- [x] Tests: ordering by every new key returns deterministic rows
- [x] Tests: column registry round-trips through settings

### Phase 2 — Frontend table scaffold — DONE

- [x] `browser-table.vue` (plain `<table>` with sticky thead — v-data-table-server's internal scroller competed with the page scroller; see commit log)
- [x] Wire `loadBrowserPage` to consume new fields when `viewMode === 'table'`
- [x] Header-click sorting → patches `orderBy`/`orderReverse`; render arrows
- [x] View-mode toggle button in top toolbar; hide order-by/reverse in table mode
- [x] Default column set per top-group rendered from registry
- [x] Click row (outside checkbox) → opens reader/group like a card click

### Phase 3 — Bulk selection in table — DONE

- [x] Checkbox column wired to `useBrowserSelectManyStore`
- [x] Header checkbox = select-all-on-page (with indeterminate state)
- [x] Existing select-many toolbar appears unchanged
- [x] Side fix: `selectAll()` reads from `page.rows` when present (was a no-op in table mode)

### Phase 4 — Column picker dialog — DONE

- [x] `browser-table-column-picker.vue` — grouped checkbox lists (Identity / Publishing / Counts / Files / Dates / Tagging / Reader / Tags & People + Other for orphans)
- [x] "Reset to defaults" button
- [x] Persist via existing `setSettings()` flow
- [x] Keyboard accessible (Vuetify v-checkbox + v-dialog defaults)

### Phase 5 — Mobile / responsive — DONE

- [x] Viewport-driven auto-fallback to cover view (Vuetify smAndDown)
- [x] Unified `BrowserPageSerializer` emits both shapes so rotation doesn't refetch
- [x] Toolbar respects fallback (column-picker hidden, order-by/reverse restored)

### Phase 6 — Polish — DONE

- [x] Cover-thumbnail column sticky on horizontal scroll (with checkbox)
- [x] Tooltips for truncated long-text cells (native `title` attribute)
- [x] Cover image fallback to placeholder svg on load error
- [x] Type-aware formatters: size → prettyBytes, dates → DATE_FORMAT, datetimes → getDateTime
- [x] Cover column shrinks to thumbnail width
- [x] Selected-row tint persists on sticky cells
- [ ] Empty / filtered-empty states — left to existing `BrowserEmptyState`; confirm in browser
- [ ] Performance audit on libraries with 50k+ comics — needs real fixture; deferred

### Phase 7 — Future hooks (out of scope for v1)

- **Inline cell editing** — registry already carries `editable` +
  `edit_widget`.
- **Multi-column sort** — extend `order_by` to a list.
- **M2M-field sorting** — experiment with sortable `genres`, `tags`,
  `characters`, `credits` columns. Likely strategies: sort by the
  first M2M element's name (cheap, somewhat arbitrary), sort by the
  joined string aggregate (correct but expensive on large
  libraries), or sort by count. May land as a `sortable_m2m` flag
  in the column registry plus a per-column annotation strategy.
  Decide based on profiling once the table view is in real use.
- **Saved column-set presets** — per-user named column layouts.
- **Per-top-group view-mode** — promote `view_mode` from a single
  scalar to a per-top-group JSON map (mirroring the column-visibility
  map). v1 ships global; revisit after dogfooding to see whether
  users actually want covers in some top-groups and table in others.
