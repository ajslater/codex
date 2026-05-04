# 03 — Hot-path render allocations

The long tail. Each item is a 3-15 line fix; impact compounds
across the dozens-to-hundreds of items rendered on a typical
browser page or metadata dialog. Suggest **two PRs**, split by
area, since touching the browser store and the metadata store
in the same PR over-couples concerns.

## PR A — Browser-side hot paths

### P1: pager scroll throttle

(Reader concern — handled in sub-plan 04. Listed here only for
the cross-reference; don't ship in this PR.)

### P3: `cards = [...groups, ...books]` per render

`components/browser/main.vue:61-64`. The spread allocates a
fresh array on every store update, even when `groups` and
`books` are unchanged.

**Fix**: move to a Pinia getter that's memoized by Pinia's own
subscription tracking, or use a stable computed that returns
`groups` directly when `books.length === 0` and skip the spread:

```js
cards() {
  const { groups = [], books = [] } = state.page;
  if (groups.length && !books.length) return groups;
  if (books.length && !groups.length) return books;
  return [...groups, ...books];
}
```

For the typical page (one or the other is empty), no allocation.

### P4: deep watcher on settings

`components/browser/drawer/browser-settings-saved.vue:112-117`
watches the entire settings tree with `deep: true`. Fires on
any nested mutation.

**Fix**: replace with shallow watchers on the specific sub-keys
the saved-settings list cares about (typically `filters` and
`search`).

### P5: `Object.freeze(page)` per nav

`stores/browser.js:584` deep-freezes the entire page payload
(50KB+ on a large library) every time the user navigates.
`Object.freeze` is `O(properties)`.

**Fix**: switch to `markRaw(page)`. Pinia tracks the reference;
deep-freezing was being used as a "don't react inside" hint —
`markRaw` is the documented way. Verify no deep watchers depend
on the inside being reactive (audit before flipping).

### P8: `card.ids.join(",")` per card per render

`components/browser/card/card.vue:98-100`. Stable input, dynamic
allocation.

**Fix**: API can return the joined string; or memoize at the
component level via a computed that depends on `item.ids`:
Vue's caching kicks in if the dependency hasn't changed.

Actually Vue computeds already do this — verify that `ids` is
the same array reference across renders. If yes, the `.join`
runs once. If no (the API returns a fresh array per fetch), the
fix is upstream — return a string field on the API.

### P9: per-card double `setTimeout(100)` on mount

`components/browser/card/card.vue:121-153`. Two sequential 100ms
timers fire on every card mount. With 100 cards, 200 timers
queued.

**Fix**: replace the timers with `requestAnimationFrame` for
DOM-measurement steps. Single rAF per card; no thread-blocking
queue.

### P10: `order-by-caption` Date+regex per render

`components/browser/card/order-by-caption.vue:41-72`. Computed
unconditionally constructs `new Date()` and runs regex tests
even for the common `sort_name` / `null` case.

**Fix**: early-return at the top of the computed for the
hide-sort cases. ~5 LOC.

### P11: `vuetifyItems` rebuild + sort per render

`components/browser/toolbars/top/filter-sub-menu.vue:140-178`.
Builds the items array via mutating loop on every render.

**Fix**: replace mutating `for...push` with `.map().filter()`
chains so the result is structurally stable when inputs are.
Memoize at the computed level.

### P12: `orderByChoices` rebuilt per render

`stores/browser.js:128-143`. Iterates the choice array per
render with conditionals.

**Fix**: this is already a getter; Pinia memoizes getters per
state. Verify it actually re-runs more than expected — if so,
the dependency tracking is fine and the fix is to narrow the
dependencies. Otherwise drop from the list.

### P13: `_filterSettings` rebuild per cover/metadata load

`stores/browser.js:235-254`. Rebuilds the same filtered settings
~1k times per session.

**Fix**: cache the result keyed on the input shape. A
`WeakMap<Settings, FilteredSettings>` keyed by the settings
object identity works because Pinia returns stable references
unless the state mutates.

### P15-P17 + P19: admin/stats/library hot paths

`components/admin/tabs/stats-tab.vue:93-162` (six computeds
each iterating stats); `library-table.vue:140-167` (headers
rebuilt; no virtualization); `job-tab.vue:228-394` (two
expensive methods called from the template); `metadata.js:216-245`
(`mapTag` rebuild per call).

**Fix**: these are all the same shape — extract a single
memoized helper. `useMemo` pattern via a computed property
keyed on the relevant input. Library-table specifically should
adopt `<v-virtual-scroll>` if installs reach 100+ libraries.

## PR B — Metadata-side hot paths

### P6: `_mappedCredits` rebuild per access

`stores/metadata.js:102-125`. Every metadata dialog access
re-iterates and rebuilds the role map. Pinia getters memoize
on tracked dependencies, but this getter accesses
`_mappedCredits` from another getter creating a chain.

**Fix**: collapse the chain into a single getter that returns
both the credit map and sorted roles. One pass over credits;
single re-trigger condition.

### P7: metadata-text overflow detection

`components/metadata/metadata-text.vue:113-126`. Per-field
`clientHeight` vs `scrollHeight` check forces layout. With 20+
fields per metadata dialog, this is 20+ forced layouts on
mount.

**Fix**: use `IntersectionObserver` (already supported
broadly). Or batch the measurements via `requestAnimationFrame`
so the layout happens once for all fields together.

### P14: `getBookSettings` `structuredClone` per call

`stores/reader.js:186-223`. `structuredClone(SETTINGS_NULL_VALUES)`
on every book settings access; the source is a frozen sentinel
that doesn't need cloning.

**Fix**: replace `structuredClone(...)` with `Object.assign({}, SETTINGS_NULL_VALUES)`
or just iterate keys directly without cloning anything.

### P18: metadata-chip theme lookup per chip

`components/metadata/metadata-chip.vue:92-95`. Reads
`this.$vuetify.theme.current.colors[...]` per chip per render.
Dozens of chips per page.

**Fix**: pull the theme color into a parent-scope computed
once, pass down via prop. Or use CSS custom properties so the
binding is at the stylesheet level.

## Correctness invariants

- **`markRaw` vs `Object.freeze`** (P5): `markRaw` opts the
  object out of Pinia's proxy, so identity comparisons still
  work. `Object.freeze` was preventing inadvertent mutation;
  `markRaw` doesn't. Audit consumers — none should be writing
  to the page object regardless.
- **Memoization keyed on object identity** (P13): only safe
  while the input reference is stable. Break the cache on store
  mutation by including a version counter or by relying on
  Pinia's automatic invalidation.
- **`requestAnimationFrame` cleanup** (P9, P7): cancel the
  pending rAF in `beforeUnmount`. Same shape as the timer
  cleanup in the bug list.

## Risks

- **`markRaw` migration** (P5) is the biggest single change.
  Worth a separate commit so it can be reverted on its own.
- **Eager memoization can leak**: keep the WeakMap (P13)
  scoped per-store; don't promote to module-level.
- **Per-render computed audits drag long**: bias toward
  shipping the obvious wins (P3, P5, P9, P10, P14, P18) and
  leaving the marginal ones (P12, P19) until after measurement
  shows them on the path.

## Suggested commit shape

Two PRs:

- **PR A — browser hot paths**: P3, P5, P8, P9, P10, P11, P13,
  P15-P17. ~150 LOC.
- **PR B — metadata + reader-store hot paths**: P6, P7, P14,
  P18, P19. ~80 LOC.

Total ~230 LOC.

## Test plan

- For each P# item, profile the same flow before/after with
  Chrome DevTools' Performance tab. Look for a frame-time
  drop on the relevant interaction.
- The aggregate impact is best measured by scrolling through a
  1k-book library in the browser and checking sustained frame
  rate.
