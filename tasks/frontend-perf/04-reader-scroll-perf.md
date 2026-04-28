# 04 — Reader scroll, prefetch, bookmark

Reader-specific perf. Bundled together because they all touch
the same scroll/prefetch/bookmark loop and benefit from
landing as one coherent change. ~150 LOC, single PR.

## S1: Bound the prefetch window

`stores/reader.js:786` `prefetchBook` generates `<link
rel="prefetch">` tags for every page (0 to maxPage). On a
1000-page omnibus that's 1000 link tags; the browser parser
allocates them all up front and the network layer queues them
all serially.

**Fix**: window the prefetch around the current page. Pages
within `[page - K, page + K]` get prefetch tags; everything
else gets an empty array. Update on each page change.

```js
const PREFETCH_WINDOW = 50;

prefetchBook() {
  const start = Math.max(0, this.page - PREFETCH_WINDOW);
  const end = Math.min(this.maxPage, this.page + PREFETCH_WINDOW);
  return this._prefetchLinksForRange(start, end);
}
```

The window of 50 is a guess; benchmark on slow networks. Too
narrow and the user feels stutter on the boundary; too wide
and we're back to the 1000-link state.

## S2: Throttle the scroll handler

`components/reader/pager/pager-vertical.vue:7`:

```html
<v-scroll:#verticalScroll="onScroll" />
```

No throttle. Fires on every pixel of scroll.

**Fix**: throttle to 50-100ms. The handler updates `page` based
on scroll position; user-perceptible page-number updates only
need ~10-20Hz, not the 100+Hz the scroll event fires at.

```js
import { useThrottleFn } from "@vueuse/core";  // already a dep

setup() {
  const onScroll = useThrottleFn(this._onScrollImpl, 100);
  return { onScroll };
}
```

Or vanilla rAF-based throttle if `@vueuse/core` isn't
available. Verify — the project already uses Vuetify and Vue;
add `@vueuse/core` if missing, it's a small targeted dep.

## S3: Coalesce bookmark API calls

`stores/reader.js:498-508`: `_setBookmarkPage` fires per page
change. With vertical scroll firing rapid page changes, this
queues many API calls.

**Fix**: debounce by `~1s`. Server only needs the final
position; an intermediate write that gets overwritten 200ms
later is wasted work.

```js
import { debounce } from "lodash-es";  // or a tiny inline helper

actions: {
  _setBookmarkPage: debounce(async function (page) {
    await API.setBookmark(page);
  }, 1000)
}
```

Combine with B3 (error handling) from sub-plan 01.

## S4: Tighten the eager window

`components/reader/pager/pager-horizontal.vue:19`:

```html
:eager="page >= storePage - 1 && page <= storePage + 2"
```

±1 / +2 keeps 4 pages mounted. For a horizontal pager that's
overkill — the user sees 1 (or 2 in two-page mode) at a time.

**Fix**: ±1 only:

```html
:eager="page >= storePage - 1 && page <= storePage + 1"
```

Saves ~100KB of decoded image memory per cached extra page on
typical comic art.

## S5: Memoize prefetchLinks

`stores/reader.js:764-778` `prefetchLinks` recomputes per
render via the pager's `head()`.

**Fix**: this becomes moot if S1's windowing landed (the link
list is already small and the dependency graph keys on `page`
+ `pk` cleanly via Pinia). Verify after S1; drop if redundant.

## S6: Throttle keyboard nav

`components/reader/toolbars/nav/reader-toolbar-nav.vue:107-127`:
no debouncing on `keyup`. Holding `j` fires 30 page-advance
calls/sec; only the last one's effect is visible (later calls
race), but the API gets hit repeatedly.

**Fix**: on each handler, gate by `lastKeyTime` or use
`keydown` with an explicit `event.repeat` check:

```js
onKey(e) {
  if (e.repeat) {
    if (Date.now() - this._lastNavTime < 100) return;
    this._lastNavTime = Date.now();
  }
  // ...
}
```

## S7: Replace `programmaticScroll` timeout with `onscrollend`

`components/reader/pager/pager-vertical.vue:121-133` sets
`programmaticScroll = true`, calls `scrollToIndex`, then waits
`250ms` before setting it back to `false`. If the user scrolls
during that window, their scroll is dropped.

**Fix**: use `scrollend` event when available; fall back to
the timeout for older browsers.

```js
scrollToPage(page) {
  this.programmaticScroll = true;
  vs.scrollToIndex(page);
  const reset = () => { this.programmaticScroll = false; };
  if ("onscrollend" in window) {
    window.addEventListener("scrollend", reset, { once: true });
  } else {
    setTimeout(reset, 250);
  }
}
```

## Correctness invariants

- **S1**: pages outside the window must still load when navigated
  to (link tags are a hint, not a requirement; the actual
  fetch happens when the page comes into view).
- **S3**: debounced bookmark must flush on book-close /
  unmount. Add a `flush()` call in `beforeUnmount` and on the
  explicit "close book" path.
- **S6**: throttle the action, not the event handler binding —
  ensure the user's intent of "advance multiple pages" is
  preserved even if it takes proportionally longer.
- **S7**: `scrollend` is one-shot; the listener removes itself
  via `{ once: true }`. Otherwise timeout-fallback path leaks.

## Risks

- **S1 window cutoff visible during fast scroll**: a user
  scrolling rapidly past the window edge might see a brief
  delay on the boundary pages. Empirically a 50-page window
  hides this on modern home networks; verify on slow
  connections before committing to a number.
- **S3 debounced bookmark on disconnect**: if the user closes
  the tab mid-debounce, the last position is lost. Mitigation:
  `navigator.sendBeacon` on `beforeunload` for the final
  bookmark write. Out of scope for this PR; track separately.
- **S7 `onscrollend` timing on iOS Safari**: `onscrollend`
  fires later than expected during inertia scrolling on iOS.
  Acceptable — the user can't initiate a page change during
  inertia anyway.

## Suggested commit shape

One PR, one commit per item. Total ~150 LOC. Related but
independent — each is its own scope.

## Test plan

- S1: open a 500-page book; verify the DOM has ~100 prefetch
  link tags (50 ahead + 50 behind capped), not 500.
- S2: scroll a vertical pager rapidly; verify `onScroll` fires
  ~10Hz, not 100Hz (devtools profiler).
- S3: scroll through 20 pages in 5 seconds; verify exactly one
  bookmark API call fires after the final stop, not 20
  in-flight.
- S4: navigate forward in horizontal mode; verify `<v-img>`
  count is 3 mounted at any time, not 4-5.
- S6: hold `j`; verify page advances at ~10Hz, not 30Hz.
- S7: programmatically scroll then immediately user-scroll;
  verify the user's scroll isn't dropped.
