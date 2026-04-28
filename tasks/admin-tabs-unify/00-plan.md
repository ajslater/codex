# Admin Flags + Jobs tabs — visual unification

## Current state

The two tabs render the same shape of content — a list of titled
sections containing rows of items — in completely different visual
languages.

### Jobs tab (`components/admin/tabs/job-tab.vue`)

- Top-level `<div id="jobs">` capped at `max-width: 700px`,
  centered.
- Each section is a `<div class="jobGroup">` with a `<h3>` header
  (`.groupHeader`, optional Stop button next to it).
- Each row is a `<div class="jobCard">`:
  - 12px padding, 8px vertical margin
  - 5px border-radius
  - `surface-light` background
  - 3px transparent left border that goes primary when active
  - flex layout: title/desc on the left, action buttons on the
    right
- Sub-status panel expands inside the card with its own divider
  (`border-top` + 6px padding) and progress bars.

The visual hierarchy reads cleanly: page → section heading →
clearly-bounded item card → action.

### Flags tab (`components/admin/tabs/flag-tab.vue`)

- Top-level `<v-table id="flags-table" striped="odd">` with a
  `<thead>` (Description / Value / Enabled) and one `<tbody>` per
  group.
- Each section header is `<tr class="flagGroupHeader"><th
  colspan="3">…</th></tr>` — a row inside the table.
- Each flag is a `<tr>` with three `<td>`s:
  - col 1 — name + description text
  - col 2 — value control (text field for banner, select for age
    ratings, select for default view; some rows skip this and let
    col 1 colspan=2)
  - col 3 — enabled checkbox / save button / nothing
- No card chrome. Stripes alternate background, but rows
  blend into one another.

The section header looks like just another row of the table —
bolder, slightly more padding, a thin bottom border. There's no
visual "lift" or grouping beyond the bold text. The next data row
abuts it immediately; rows inside a group flow continuously into
rows of the next group.

### The problems

1. **Two completely different design languages** for the same
   shape of content (sections of items). Anyone bouncing between
   the two tabs feels the visual whiplash.
2. **Flags' section headers don't read as headers** — they're
   styled like rows because they *are* rows. The `colspan="3"`
   trick gives them the full width but the row context glues them
   to the data immediately below.
3. **Flag rows have no boundary** — the table-stripe pattern is
   the only thing distinguishing one flag from the next, and it's
   weak compared to the Jobs cards.

## Proposed unified design

Adopt the Jobs tab's visual language for both. Concretely:

- **Section header**: outside any card, an `<h3>` left-aligned
  with optional action button(s) on the right. Matches today's
  Jobs `.groupHeader`.
- **Item card**: `<div>` with the same chrome as Jobs'
  `.jobCard` — surface-light bg, padding, rounded corners.
  Optional left-border accent stays a Jobs-only feature
  (signals "active" — Flags has no equivalent state).
- **Container width**: 700px max, centered. Flags are short rows;
  capping the width keeps a comfortable line length for the
  description text and prevents form controls from stretching to
  unreadable widths.

Both tabs share the same:

- Section spacing (`margin-top` between groups)
- Header typography (h3 size + weight)
- Card chrome (background, padding, radius)
- Description text style (textSecondary, 0.85em)

Tabs differ only where their *content* differs:

- Jobs cards have an action area (Start/Stop) and an
  expand-to-status panel.
- Flag cards have a value control (input/select/checkbox)
  inside the card body.

## Implementation

### Shape of the change

One PR. No behavioral changes to either tab — pure markup +
styles. Touches three files:

1. **New** `components/admin/tabs/admin-section.scss` (or just a
   new top-level scope in the Jobs file's existing styles
   `@use`'d from Flags). Holds the shared chrome:

   ```scss
   .adminGroup { margin-top: 1em; }
   .adminGroupHeader {
     display: flex;
     align-items: center;
     justify-content: space-between;
   }
   .adminCard {
     padding: 12px;
     margin: 8px 0;
     border-radius: 5px;
     background-color: rgb(var(--v-theme-surface-light));
   }
   .adminCardActive {
     border-left: 3px solid rgb(var(--v-theme-primary));
   }
   .adminContainer {
     max-width: 700px;
     margin-left: auto;
     margin-right: auto;
   }
   ```

   Also lifts the shared item-row internals (title +
   description text styles).

2. **Edit** `flag-tab.vue`:
   - Drop `<v-table>` entirely.
   - Top-level: `<div class="adminContainer">`.
   - Per group: `<div class="adminGroup">` with a `.adminGroupHeader`
     (h3 inside).
   - Per flag: `<div class="adminCard">`. Inside the card:
     - Header row: title + (when applicable) the value control
       and/or the checkbox aligned right.
     - Body: description text.

   Layout sketch for a flag card:

   ```
   ┌────────────────────────────────────────────────┐
   │ Flag Title                          [✓ enable] │
   │ Description text on the next line.             │
   │ (when applicable: input or select control)     │
   └────────────────────────────────────────────────┘
   ```

   For the four "value-bearing" flags (BT banner, AR/AA age
   ratings, BG default view) the control replaces the checkbox;
   the checkbox slot sits empty for those.

3. **Edit** `job-tab.vue` only to rename classes to the shared
   names (`jobCard` → `adminCard`, `jobGroup` → `adminGroup`,
   etc.) and pull from the shared scss. The `jobCardActive`,
   `jobHeader`, `jobInfo`, `jobActions`, `jobStatusSection`, and
   `statusRow*` styles stay job-local since Flags has no
   equivalent.

### Step-by-step

1. Land the shared styles file with the basic chrome.
2. Migrate Jobs to use the shared classes. Should be a no-op
   visual change — verify by side-by-side screenshot.
3. Rewrite Flags' template to use the new card layout. This is
   the only step that's user-visible.
4. Confirm both tabs render correctly across the existing flag
   and job inventory:
   - Flags: 9 keys across 4 groups (Access & Privacy, Browser
     Display, Metadata Import, System) plus the orphan-collector
     "Other" group.
   - Jobs: 6 groups (Libraries, Search, Covers, Notify, Janitor,
     Library Maintenance) including the Notify select-style
     group and the variant-bearing Update Libraries / Update
     Custom Covers cards.
5. Lint, test, build.

### Risks / open questions

- **The 700px cap on Flags**: today's Flags table is full-width.
  Capping it does shrink content area on a wide monitor, but
  the line lengths it produces match Jobs (which already uses
  the cap and reads fine). If real-world feedback is "I want
  the wider table back", we can opt the wide controls (banner
  text field) out of the cap.
- **Mobile layout**: the table flows on small screens because
  it's a table. The card layout will stack title/desc/control
  vertically; should look better on narrow viewports than the
  table did, but worth a manual check.
- **The "Other" orphan group on Flags**: stays in place — it's a
  defensive fallback for server-released flags the frontend
  doesn't know about. The unified design surfaces it the same
  way as a normal group.
- **No behavior changes**: change is pure presentation. The
  ``changeCol`` action wiring, error binding, ``loadTables``
  call, etc. all stay identical.

### Out of scope

- Keyboard navigation parity between tabs.
- Reordering or regrouping flags / jobs (sub-plan was already
  shipped for Flags grouping in PR #644).
- Vuetify component swaps (e.g. moving from native checkbox to
  v-switch). Save those for the `js-vue-quality-pass.md`
  cleanup.

## Test plan

- Manual: open `/admin/flags`, verify section headers stand
  apart from item cards, the BT/AR/AA/BG cards render their
  controls, the standard checkbox cards toggle, and changes
  persist via the API.
- Manual: open `/admin/jobs`, verify nothing changed visually
  vs. main.
- Manual: shrink the viewport to mobile width, verify both tabs
  still read cleanly.
- `bun run lint`, `bun run test:ci`, `bun run build`.

Total work: ~150 LOC change in `flag-tab.vue` (mostly template
restructure), ~30 LOC in `job-tab.vue` (class renames), ~40 LOC
in the new shared styles file.
