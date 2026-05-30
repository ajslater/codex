# Codex Admin Design Language

The browser and reader UIs already share a calm, consistent language (one theme,
shared toolbars, `v-card` panels). The **admin** area grew tab by tab and
drifted: three table styles, four copies of the Save/Revert bar, help text in
two different greys, and a binary 700px-or-full-width layout applied
inconsistently. This document is the single source of truth for the admin visual
language. New admin UI **composes the primitives below** rather than re-styling
from scratch.

Scope: `frontend/src/components/admin/`. The tokens and rules here are admin-
first but intentionally compatible with the rest of the app's theme
(`src/plugins/vuetify.js`).

---

## 1. Layout law

Two — and only two — content widths:

| Content kind                                                              | Width                                                  | Rule                                                                                                                                |
| ------------------------------------------------------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Data tables** (users, groups, libraries, custom covers, failed imports) | **Full bleed**                                         | Span the tab's full width so as many columns as possible are visible. This is a deliberate utility choice — never cap a data table. |
| **Forms, settings, prose, key/value tables**                              | **Reading column** (`$reading-width`, 760px), centered | Everything you _read_ or _fill in_ sits in one comfortable column, the same width on every tab.                                     |

The reading column is **centered** (`margin-inline: auto`) — the same column on
every tab, including the settings/help that sit below a full-bleed table on the
Users, Groups, and Libraries tabs.

Use `.adminReadingColumn` for the reading column. Never re-cap width with a
local `max-width` on a tab root.

## 2. Spacing & radius scale

Defined in `tabs/design.scss`. Stop hand-typing `8px` / `12px` / `2em`.

| Token        | Value | Use                             |
| ------------ | ----- | ------------------------------- |
| `$space-1`   | 4px   | icon gaps, tight insets         |
| `$space-2`   | 8px   | default gap between controls    |
| `$space-3`   | 12px  | card padding                    |
| `$space-4`   | 16px  | gap between cards / action bars |
| `$space-6`   | 24px  | gap between sections            |
| `$space-8`   | 32px  | major separation (prose blocks) |
| `$radius`    | 5px   | cards                           |
| `$radius-sm` | 3px   | inline chips/code/status rows   |

## 3. Type scale & text roles

| Token         | Size       | Use                             |
| ------------- | ---------- | ------------------------------- |
| `$text-title` | 1rem / 500 | section `<h3>` and card titles  |
| `$text-body`  | 0.9em      | default body                    |
| `$text-small` | 0.85em     | descriptions, hints, help prose |
| `$text-meta`  | 0.8em      | timestamps, counts, "last run"  |

**Text-colour roles are fixed — do not swap them per tab:**

| Theme colour              | Role                                                             |
| ------------------------- | ---------------------------------------------------------------- |
| `textPrimary` (#FFF)      | titles, primary values                                           |
| `textHeader` (#D3D3D3)    | toolbar/heading chrome                                           |
| `textSecondary` (#A9A9A9) | **all** help/description/prose body                              |
| `textDisabled` (#808080)  | **only** de-emphasised meta: timestamps, counts, disabled values |

Before this spec, help text was `textSecondary` on some tabs and `textDisabled`
on others. Help/explanatory prose is **always `textSecondary`**.

## 4. Primitives

Prefer these over bespoke markup. Each enforces the language so it can't drift.

### Components (in `src/components/admin/tabs/`)

- **`AdminSection`** (`admin-section.vue`) — a titled block. `title` prop,
  optional `hint` prop or `#hint` slot, optional `#actions` slot (header-right,
  e.g. a Stop or Add button). Replaces the `.adminGroup` + `.adminGroupHeader` +
  `<h3>` markup.
- **`AdminActionBar`** (`action-bar.vue`) — the Save / Revert (or Save / cancel)
  row. Primary button is `type="submit"` `tonal`; secondary is `text`. Props
  `saveText`, `saving`, `saveDisabled`, `revertDisabled`; emits `revert`.
  Replaces the four copies of `.settingsActions`.
- **`AdminExpandToggle`** (`expand-toggle.vue`) — the chevron + label disclosure
  used for sub-status and log panels. `v-model` (expanded) + `label`. Replaces
  the two copies of `.expandToggle`.
- **`AdminKeyValueTable`** (`key-value-table.vue`) — a label→value table (stats,
  restore counts). One look for every key/value readout. Data/CRUD tables stay
  on `AdminTable`.

### Shared classes (`tabs/admin-section.scss`)

- `.adminReadingColumn` — §1 reading column.
- `.adminCard`, `.adminCardActive`, `.adminCardHeader`, `.adminCardInfo`,
  `.adminCardTitle`, `.adminCardDesc`, `.adminCardActions` — the card system.
- `.adminActionCell` — the icon-button cluster in a table's Actions column
  (dimmed to 0.7, full opacity on hover). Replaces `.actionButtonCell`.
- `.adminFieldColumn` — a vertical stack of inputs (gap `$space-2`). Replaces
  `.credentialFields`.
- `.adminInlineActions` — a horizontal row of buttons. Replaces
  `.credentialActions`.
- `.adminProse` — help/intro prose: reading width, `$text-small`,
  `textSecondary`. Replaces `.adminIntro`, `#ageRatingHelp`, `#libraryHelp`,
  `#groupHelp`.
- `.adminHint` — a one-line hint under a section header.
- `.adminKvTable` — backing style for `AdminKeyValueTable` and any inline
  key/value `<table>`.
- `.adminCode` — inline `<code>` chips.

## 5. Tables

Three kinds, three (and only three) treatments:

1. **Data / CRUD tables** → `AdminTable` (wraps `v-data-table-virtual`), **full
   bleed**, sortable, `fixed-header`. Row Actions use `.adminActionCell`.
2. **Key/value readouts** → `AdminKeyValueTable` (stats, restore counts).
3. **Reference matrices** (the Groups access-logic truth table) → a plain
   `<table class="adminMatrix">` using shared border/padding tokens; semantic
   cell colours (`includeGroup` / `excludeGroup`) are allowed there.

No more raw hand-bordered `<table>` per tab.

## 6. Buttons

| Intent                                      | Treatment                                                              |
| ------------------------------------------- | ---------------------------------------------------------------------- |
| Section primary (Save, Snapshot Now, Start) | `variant="tonal"`                                                      |
| Secondary (Revert, Test, Clear)             | `variant="text"`                                                       |
| Destructive                                 | `color="error"`, always behind `ConfirmDialog`                         |
| Table row actions                           | icon button, `size="small"` `density="compact"`, in `.adminActionCell` |

Sizes: section actions `size="small"`; row actions
`size="small" density="compact"`. Don't mix the default (large) variant into
compact rows.

## 7. Dialogs & confirmation

- **One header look** for modal dialogs. `ConfirmDialog`'s `.title` is the
  canonical treatment (bolder, `larger`); the create/update form's `.cuTitle`
  mirrors it so the two admin dialogs match instead of one using `<h2>` and the
  other a `.title` div.
- **Never use the browser-native `confirm()`** for destructive admin actions —
  always the `ConfirmDialog` component, so the confirmation looks like the rest
  of the app and is theme-styled. `ConfirmDialog` takes `variant` / `color`
  props so it can render as a text, tonal, or icon button in place.

## 8. Checklist for a new admin tab

- [ ] Forms/prose in `.adminReadingColumn`; data tables full-bleed.
- [ ] Sections via `AdminSection`; cards via `.adminCard`.
- [ ] Save/Revert via `AdminActionBar`; disclosures via `AdminExpandToggle`.
- [ ] Help prose via `.adminProse` (always `textSecondary`).
- [ ] Spacing/type from the scale; no new magic numbers.
- [ ] Destructive actions via `ConfirmDialog`; buttons follow §6.
