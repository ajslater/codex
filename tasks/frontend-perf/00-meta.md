# Frontend perf + correctness — meta plan

`frontend/src/` is large (~12k LOC components + ~3.5k LOC
stores/api/plugins, 170 .js/.vue files). The investigation
itself was fanned across four parallel surveys (browser, reader,
API/socket, admin/metadata) plus the build config. This document
synthesizes the findings, ranks them, and groups them into
ship-as-PR sub-plans.

## Why now

The backend has had multiple perf passes (importer #628–634,
janitor #635–640, librarian threads #641, admin flag UX #643–644).
The frontend has had narrower work (cover cleanup, OPDS v2 batching,
admin views perf). A holistic survey finds that the frontend
carries a few real correctness bugs that risk silent data loss
and a long tail of per-render allocations that add up on large
libraries / long reading sessions.

## Surface map

| Area | Source | Approx LOC | Largest single file |
| --- | --- | --- | --- |
| Browser | `stores/browser.js` + `components/browser/` | 716 + 3.5k | `browser.js` (716) |
| Reader | `stores/reader.js` + `components/reader/` | 796 + 3k | `reader.js` (796) |
| Admin | `stores/admin.js` + `components/admin/` | 221 + 2.5k | `job-tab.vue` (631) |
| Metadata | `stores/metadata.js` + `components/metadata/` | 250 + ~600 | `metadata-text.vue` |
| Auth / common | `stores/auth.js`, `stores/common.js` | 118 + 98 | — |
| API | `api/v3/*.js` | ~700 | `browser.js` (151) |
| Socket | `stores/socket.js` | 201 | — |
| Plugins | `plugins/router.js`, `vuetify.js`, `drag-scroll.js` | ~240 | — |

## Findings (ranked)

### Tier 1 — correctness bugs

These risk silent data loss, race conditions, or features that
silently never work. **Ship first.**

| # | File:line | Issue | Risk |
| - | --- | --- | --- |
| B1 | `components/reader/pager/page/page.vue:104` | `setTimeout(function () { if (!this.loaded) ... })` non-arrow → `this` lost; the load-progress spinner literally never shows | UX: long-loading pages give the user no feedback |
| B2 | `stores/reader.js:486` | `arcs.push({ r: "0" })` wrong shape; sibling code uses `{ group, pks }` | API call returns 500 on the no-arcs fallback |
| B3 | `stores/reader.js:371-380, 498-508` | `_setBookmarkPage` not awaited, errors swallowed | User loses reading position on network blip; silent |
| B4 | `stores/reader.js:413-475` | `loadBooks` no AbortController; rapid Next-Book clicks race | Settings from earlier book overwrite the later one |
| B5 | `stores/browser.js:562-601` | `loadBrowserPage` no AbortController; route-change races | Stale page response wins; user sees wrong group's data |
| B6 | `api/v3/common.js:115` | `revokeObjectURL(response.data)` passes blob instead of `link.href` | iOS PWA blob URL leak per download |
| B7 | `stores/auth.js:81-87` | `logout()` not awaited before clearing user state | Window where user is "logged out" client-side but server still has session |
| B8 | `api/v3/browser.js:92` | `getGroupDownloadURL` mutates input via `delete settings.show` | Caller's settings object silently modified |
| B9 | `components/browser/toolbars/search/search-combobox.vue:54-58` | Search history `unshift` with no size cap | Unbounded growth in long sessions |
| B10 | `components/browser/toolbars/top/filter-sub-menu.vue:51-57, 159` | Both Vuetify `:items` prop AND template `v-for` render the list | Each list item rendered twice (DOM + memory) |
| B11 | `components/admin/tabs/job-tab.vue:124` | `@click="loadAllStatuses"` on the entire expand-row container | Status API refetched on every UI expand toggle |
| B12 | `components/metadata/metadata-dialog.vue:124-138` | `setTimeout` in `updateProgress` not cleared on unmount | Null-ref errors if dialog closes mid-animation |
| B13 | `components/reader/pager/pager.vue:50-60` | Dynamic `<component :is>` switch lacks `:key` | Old pager's scroll listeners persist after orientation swap |

### Tier 2 — hot-path render allocations

Per-render allocations and cascading computeds on lists / dialogs
that render dozens-to-hundreds of items. Each is small; together
they dominate render frames on large libraries.

| # | File:line | Issue |
| - | --- | --- |
| P1 | `components/reader/pager/pager-vertical.vue:7` | `v-scroll` fires on every pixel; no throttle |
| P2 | `stores/reader.js:786` | `prefetchBook` generates link tags for ALL pages on a 1000-pg book |
| P3 | `components/browser/main.vue:61-64` | `cards = [...groups, ...books]` allocates fresh array per render |
| P4 | `components/browser/drawer/browser-settings-saved.vue:112-117` | Deep watcher on entire settings object |
| P5 | `stores/browser.js:584` | `Object.freeze(page)` per nav on a 50KB+ object |
| P6 | `stores/metadata.js:102-125` | `_mappedCredits` rebuilds on every getter access |
| P7 | `components/metadata/metadata-text.vue:113-126` | Per-field overflow detection forces layout thrash |
| P8 | `components/browser/card/card.vue:98-100` | `ids.join(",")` per render across all cards |
| P9 | `components/browser/card/card.vue:121-153` | Two sequential `setTimeout(..., 100)` in mounted per card |
| P10 | `components/browser/card/order-by-caption.vue:41-72` | `new Date()` / regex inside computed per render |
| P11 | `components/browser/toolbars/top/filter-sub-menu.vue:140-178` | `vuetifyItems` rebuilds + sorts choice arrays per render |
| P12 | `stores/browser.js:128-143` | `orderByChoices` rebuilt per render |
| P13 | `stores/browser.js:235-254` | `_filterSettings` rebuilt per cover/metadata load (~1k/session) |
| P14 | `stores/reader.js:186-223` | `getBookSettings` calls `structuredClone(SETTINGS_NULL_VALUES)` per access |
| P15 | `components/admin/tabs/stats-tab.vue:93-162` | Six computed properties iterate stats objects per render |
| P16 | `components/admin/tabs/job-tab.vue:228-270, 329-394` | `isNightlyRunning` + `jobStatusSummary` rebuilt per render |
| P17 | `components/admin/tabs/library-table.vue:140-167` | `headers` computed rebuilt per render; no virtualization |
| P18 | `components/metadata/metadata-chip.vue:92-95` | `$vuetify.theme.current.colors` lookup per chip per render |
| P19 | `stores/metadata.js:216-245` | `mapTag()` rebuilds entire tag map per call |

### Tier 3 — network + dedup

Avoidable network thrash. Each item is a 1-3 line fix on the
right abstraction.

| # | File:line | Issue |
| - | --- | --- |
| N1 | `stores/browser.js:629-645` | `loadMtimes` no pending-promise dedup |
| N2 | `stores/browser.js:620-626` | `loadFilterChoices` no abort or dedup |
| N3 | `stores/socket.js:20-21` | WS reconnect fixed 3s; no exponential backoff |
| N4 | `api/v3/base.js:13-23` | CSRF token regex-extracted from cookie per request |
| N5 | `api/v3/admin.js:10,35,39` | Static admin tables refetched with `ts` per tab view |
| N6 | `stores/admin.js:107-111` | `loadTables` fires unawaited; race-prone |
| N7 | `stores/admin.js:197-211` | `loadAllStatuses` rebuilds entire map per call |
| N8 | `stores/socket.js:125-142` | `libraryNotified` triggers two parallel mtime fetches (browser + reader) |
| N9 | `api/v3/base.js:29-44` | CSRF 403 deletes sessionid but doesn't surface to user |
| N10 | `api/v3/common.js:86-96` | `loadOPDSURLs` populates lazily; first request blocks |
| N11 | `app.vue:29-33` | `setTimezone` called twice on mount race |

### Tier 4 — reader scroll / prefetch

Reader-specific perf. Bundled together because they all touch
the scroll/prefetch path.

| # | File:line | Issue |
| - | --- | --- |
| S1 | `stores/reader.js:786` (= P2) | Prefetch ALL pages of a book |
| S2 | `components/reader/pager/pager-vertical.vue:7` (= P1) | No scroll throttle |
| S3 | `stores/reader.js:498-508` | Bookmark API call per page change; not coalesced |
| S4 | `components/reader/pager/pager-horizontal.vue:19` | `:eager` window of ±2 keeps 5 pages mounted |
| S5 | `stores/reader.js:764-778` | `prefetchLinks` recomputes per render |
| S6 | `components/reader/toolbars/nav/reader-toolbar-nav.vue:107-127` | Keyboard nav not throttled; held key fires 30/sec |
| S7 | `components/reader/pager/pager-vertical.vue:121-133` | `programmaticScroll` flag with fixed 250ms timeout vs. `onscrollend` |

## Sub-plan structure

Five sub-plans, in suggested ship order:

1. **[01-correctness-bugs.md](./01-correctness-bugs.md)** —
   Tier 1 (B1-B13). Single PR. Mostly small diffs; 2-3 of them
   are one-line fixes (B1 arrow function, B2 wrong shape).
   Highest priority because correctness > perf.

2. **[02-request-dedup.md](./02-request-dedup.md)** —
   Tier 3 (N1-N11). Single PR. Adds `AbortController` plumbing
   to the navigation-driven endpoints, a pending-promise cache
   for mtime/choices, and exponential backoff on the websocket
   reconnect. Also fixes the CSRF-token cache and the admin
   static-tables timestamp.

3. **[03-hot-path-renders.md](./03-hot-path-renders.md)** —
   Tier 2 (P1-P19). Likely splits into two PRs by area:
   browser-side and metadata-side. Each item is small; the
   value comes from the aggregate.

4. **[04-reader-scroll-perf.md](./04-reader-scroll-perf.md)** —
   Tier 4 (S1-S7). Single PR. Reader-specific; ships
   independent of the others. Includes the prefetch-window
   bound, scroll throttle, bookmark coalescing.

5. **[05-bundle-and-startup.md](./05-bundle-and-startup.md)** —
   Vite chunk splitting (Vue / Vuetify / Pinia / app), startup
   parallelization, OPDS URL pre-fetch. Smaller scope; ships
   when the rest land.

## Methodology used in the survey

The investigation itself was fanned across four parallel
sub-agents with focused briefs (browser / reader / API+socket /
admin+metadata). Each returned a punch list of
file:line + impact + fix tagged `perf` or `bug`. Build-config
review was done separately. Findings were then synthesized into
the four tiers above, deduplicating items that surfaced from
multiple angles (e.g., `prefetchBook` showed up in both reader
and memory-leak axes).

This pattern (fan-out survey, synthesize) scales to surface
sizes a single pass can't cover. Used previously for the
importer-perf and janitor-perf plans.

## Out of scope

- **Deep Vuetify-4-specific stylistic cleanup**: the
  `js-vue-quality-pass.md` rules cover this and are tracked
  separately.
- **Pinia store splits / refactors**: stores/browser.js (716) and
  stores/reader.js (796) are large but the survey didn't find
  evidence the size itself causes perf problems. Split when there's
  a feature-driven reason, not as perf work.
- **Service-worker / PWA caching strategy**: separate concern from
  in-app perf.
- **Replacing xior with another HTTP client**: not justified by
  any finding.

## Risks

- **AbortController semantics on iOS Safari**: `AbortController` is
  supported in modern Safari but the abort signal on `fetch` has
  edge cases on iOS < 16.4. Sub-plan 02 will keep behavior safe
  on abort (don't crash; just suppress the late response).
- **`onscrollend` browser support**: not yet universal. Sub-plan
  04's pager-vertical fix needs a `setTimeout` fallback for
  browsers that don't fire it.
- **Reactive subtleties of `markRaw` / `Object.freeze`**: replacing
  the `Object.freeze(page)` (P5) with `markRaw` is intent-correct
  but requires verifying no deep watchers depend on identity.

## Notes on tooling

- `bun run lint` (eslint + prettier) catches the obvious nits.
- `bun run test:ci` (vitest) currently runs 1 test; the survey
  found a few candidates worth covering (the bookmark-coalesce
  path, the AbortController flow on rapid nav).
- `bun run build` produces a manifest; visual bundle inspection
  would benefit from `rollup-plugin-visualizer` for sub-plan 05.
