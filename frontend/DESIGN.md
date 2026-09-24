# Codex Admin Design Language

The browser and reader UIs already share a calm, consistent language (one theme,
shared toolbars, `v-card` panels). The **admin** area grew tab by tab and
drifted: three table styles, four copies of the Save/Revert bar, help text in
two different greys, and a binary 700px-or-full-width layout applied
inconsistently. This document is the single source of truth for the admin visual
language. New admin UI **composes the primitives below** rather than re-styling
from scratch.

Scope: `frontend/src/components/admin/` for layout, spacing, radius and type.
**§9 (Colour) and §10 (Cascade layers) apply to the whole frontend** — they
record how the app as a whole uses the theme, not an admin-only convention. The
tokens themselves live in `src/plugins/vuetify.js`.

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

| Theme colour               | Role                                                             |
| -------------------------- | ---------------------------------------------------------------- |
| `text-primary` (#FFF)      | titles, primary values                                           |
| `text-header` (#D3D3D3)    | toolbar/heading chrome                                           |
| `text-secondary` (#A9A9A9) | **all** help/description/prose body                              |
| `text-disabled` (#808080)  | **only** de-emphasised meta: timestamps, counts, disabled values |

Before this spec, help text was `text-secondary` on some tabs and
`text-disabled` on others. Help/explanatory prose is **always
`text-secondary`**.

## 4. Primitives

Prefer these over bespoke markup. Each enforces the language so it can't drift.

### Components (in `src/components/admin/tabs/`)

- **`AdminSection`** (`admin-section.vue`) — a titled block. `title` prop,
  optional `hint` prop or `#hint` slot, optional `#actions` slot (header-right,
  e.g. a Stop or Add button). Replaces the `.adminGroup` + `.adminGroupHeader` +
  `<h3>` markup. The `sub` boolean prop nests a section inside another
  AdminSection: a small uppercase overline title (h4) and an indented left rule
  make the subordination visible (see the Auth tab's OIDC block).
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
  `text-secondary`. Replaces `.adminIntro`, `#ageRatingHelp`, `#libraryHelp`,
  `#groupHelp`.
- `.adminHint` — a one-line hint under a section header.
- `.adminKvTable` — backing style for `AdminKeyValueTable` and any inline
  key/value `<table>`: striped rows, right-aligned tabular values, an
  inter-column gap so long labels never touch the value.
- `.adminCode` — inline `<code>` chips.

## 5. Tables

Three kinds, three (and only three) treatments:

1. **Data / CRUD tables** → `AdminTable` (wraps `v-data-table-virtual`), **full
   bleed**, sortable, `fixed-header`. Row Actions use `.adminActionCell`.
2. **Key/value readouts** → `AdminKeyValueTable` (stats, restore counts).
3. **Reference matrices** (the Groups access-logic truth table) → a plain
   `<table class="adminMatrix">` using shared border/padding tokens; semantic
   cell colours (`include-group` / `exclude-group`) are allowed there.

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
- [ ] Help prose via `.adminProse` (always `text-secondary`).
- [ ] Spacing/type from the scale; no new magic numbers.
- [ ] Destructive actions via `ConfirmDialog`; buttons follow §6.
- [ ] Colour via §9; scoped styles layered per §10.

---

## 9. Colour (whole frontend)

Every colour in the app comes from the theme in `src/plugins/vuetify.js`. There
are exactly two ways to reach one, and a short list of things not to do.

**In SCSS**, read the CSS variable:

```scss
color: rgb(var(--v-theme-text-secondary));
background-color: rgba(var(--v-theme-primary), 0.15);
```

The eight custom tokens are kebab-case, like Vuetify's own (`surface-light`,
`primary-darken-1`). `tests/unit/theme-contract.test.js` fails on a camelCase
`--v-theme-` variable: the old spelling resolves to nothing and the declaration
is dropped in silence.

**In a template**, pass the token's _name_ to a `color` prop, never a hex:

```vue
<v-btn color="primary" />
```

Same for component defaults in `plugins/vuetify.js` — `color: "primary"`, not
`codexTheme.colors.primary`. A resolved hex lands as an inline style on the
element and stops following the theme; the contract test fails on one.

**Do not:**

- Write a hex literal anywhere outside `plugins/vuetify.js` and
  `book-cover.scss`. (The reader's `$stack-shadow-*` values and the
  `rgba(0, 0, 0, ·)` scrims are deliberate exceptions: they are dark-theme
  constants, not theme colours.)
- Read `$vuetify.theme.current.colors` in JS to resolve a hex.
  `metadata-chip.vue` used to, per chip per render, and now returns the token
  name for the `:color` prop instead. Where JS really must produce a colour
  string, build the CSS variable from a token name — `tagging-status-table.vue`
  keeps token names in `STATUS_META` and emits `rgb(var(--v-theme-<token>))`.
- Hardcode a value Vuetify already publishes. Prefer
  `rgba(var(--v-border-color), var(--v-border-opacity))` over a literal `0.12`.

Text-colour roles are in §3 and apply everywhere, not only in admin.

---

## 10. Cascade layers (whole frontend)

The order is declared once, inline, in `codex/templates/index.html`:

```css
@layer vuetify-core, vuetify-components, vuetify-overrides,
       codex-base, codex-components,
       vuetify-utilities, vuetify-final, codex-trumps;
```

It lives there and nowhere else. A browser fixes a layer's position the first
time it sees the name, and django-vite links imported chunks' CSS — Vuetify
component chunks open with `@layer vuetify-components` — before the entry's own.
A declaration shipped through `main.js` would arrive second. Inline in the
template cannot be out of order and cannot 404.

**Where each kind of stylesheet goes:**

| Stylesheet                                                      | Layer                                               |
| --------------------------------------------------------------- | --------------------------------------------------- |
| `src/styles/global.scss`                                        | `codex-base`                                        |
| A shared SCSS partial that emits CSS                            | `codex-components`, declared **inside the partial** |
| A component's scoped `<style>` that overrides Vuetify internals | `codex-components`                                  |
| A rule that must beat a Vuetify utility class                   | `codex-trumps`, with a comment saying why           |

**What the order buys.** `codex-*` after `vuetify-components` means a codex rule
beats Vuetify's component CSS without `!important`. `codex-*` before
`vuetify-utilities` means a `color` prop still wins — which is why a snackbar
with `color="error"` paints red without the carve-out it used to need.
`codex-components` after `codex-base` lets a component's own rule beat the
global `a` rule. Never override `vuetify-final`: it holds `forced-colors`
accessibility fixes.

**Two Sass rules, both load-bearing:**

1. A partial that emits CSS **wraps its own rules** in `@layer`. `@use` emits a
   partial's CSS at the top of the consuming stylesheet, _outside_ any `@layer`
   the consumer writes, so a consumer-side wrap silently leaves the shared rules
   unlayered — and unlayered CSS beats all layered CSS.
2. `@use` inside `@layer { }` is a Sass error. Keep `@use`, `@forward` and
   `$variables` above the block.

Vue's scoping and `:deep()` both survive the wrap: the `[data-v-*]` attribute
lands inside the layer block.

**Every Vuetify stylesheet must arrive layered.** In Vuetify 4.2.1
`VPullToRefresh.sass` was missing the `@include tools.layer('components')` its
128 siblings have, so it shipped unlayered — and
`.v-pull-to-refresh { overflow: hidden }` outranked the scoped ID rule that
makes `#browsePaneRefreshContainer` the browse pane's scroller, which stopped
the browser scrolling in v2.4.0. Codex wrapped it at build time until Vuetify
4.2.2 fixed it upstream; `package.json` now floors at 4.2.2. When bumping
Vuetify, check that no stylesheet under `node_modules/vuetify/lib` lacks
`@layer`.

**`!important` is no longer the tool for beating Vuetify.** If a rule needs to
win, the answer is a layer, not a flag. 76 declarations carried it when the
theme work began; the colour ones are gone.

**A new unscoped `<style>` block is not allowed.** A shared global class goes in
`src/styles/global.scss`; anything else is scoped, or a component.
