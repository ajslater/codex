# 01 — Correctness bugs

Ships first. Each item is a small, focused fix; total ~150 LOC
across the 13 files. Group them in one PR with one commit per
unrelated bug so individual fixes can be reverted cleanly.

## B1: page.vue spinner never shows

`components/reader/pager/page/page.vue:104-108`:

```js
mounted() {
  setTimeout(function () {
    if (!this.loaded) {
      this.loading = true;  // `this` is the timer, not the component
    }
  }, PROGRESS_DELAY_MS);
}
```

**Fix**: arrow function. Also: clear the timeout on
`beforeUnmount` so a quickly-paged page doesn't fire a stray
update on a torn-down component.

```js
mounted() {
  this._loadingTimer = setTimeout(() => {
    if (!this.loaded) this.loading = true;
  }, PROGRESS_DELAY_MS);
},
beforeUnmount() {
  clearTimeout(this._loadingTimer);
}
```

## B2: arc fallback wrong shape

`stores/reader.js:486`:

```js
if (!arcs.length) {
  // No arcs is a 500 from the mtime api
  arcs.push({ r: "0" });  // wrong — adjacent code uses { group, pks }
}
```

**Fix**: `arcs.push({ group: "r", pks: "0" })`. The comment hints
the dev knew about the 500; the fallback never actually worked.

## B3: bookmark persistence loses page on errors

`stores/reader.js:371-380` + `:498-508`:

```js
async setRoutesAndBookmarkPage(page) {
  this.page = page;
  await this._setBookmarkPage(page);  // not awaited in some paths; errors swallowed
  ...
}
```

**Fix**: catch + retry once on transient errors; if it still
fails, surface a one-time toast through `useCommonStore`. Don't
revert the local page state — the user reads forward, the
bookmark catches up next request.

## B4: loadBooks rapid race

`stores/reader.js:413-475`: rapid Next-Book clicks fire
overlapping fetches; second-arriving response wins, settings
from the first arrival can stomp the second's state.

**Fix**: store an `AbortController` on the action; abort the
previous on entry, attach the new one. On abort, suppress the
response merge silently (don't `$patch`).

## B5: loadBrowserPage no AbortController

`stores/browser.js:562-601`: same shape as B4 but for the
browser. Rapid group clicks → wrong group's data displayed.

**Fix**: same pattern. The shared helper introduced in sub-plan
02 (request-dedup) handles this; reference there.

## B6: iOS PWA blob URL leak

`api/v3/common.js:115`:

```js
URL.revokeObjectURL(response.data);  // passing the Blob, not the object URL
```

**Fix**: capture `link.href` (the URL string returned from
`createObjectURL`) and pass that to `revokeObjectURL`.

## B7: logout race

`stores/auth.js:81-87`:

```js
async logout() {
  this.user = undefined;  // cleared before API call returns
  return await API.logout();
}
```

**Fix**:

```js
async logout() {
  try {
    await API.logout();
  } finally {
    this.user = undefined;
  }
}
```

The `finally` clears state even if the server-side logout fails
— the client can't trust the session anyway. But order matters:
no window where the API call is in flight with the user already
client-cleared.

## B8: getGroupDownloadURL mutates input

`api/v3/browser.js:92`:

```js
delete settings.show;  // mutates caller's settings object
```

**Fix**: destructure-and-spread:

```js
const { show, ...rest } = settings;
return ...rest;
```

## B9: search history unbounded

`components/browser/toolbars/search/search-combobox.vue:54-58`:

`unshift` adds without bounding length; `MAX_ITEMS=10` is
declared but only applied in a `.slice` elsewhere.

**Fix**: cap `this.items` at `MAX_ITEMS` after every `unshift`:

```js
this.items.unshift(value);
if (this.items.length > MAX_ITEMS) this.items.length = MAX_ITEMS;
```

## B10: filter-sub-menu double render

`components/browser/toolbars/top/filter-sub-menu.vue:51-57, 159`:

The `<v-list>` uses `:items="..."` (Vuetify renders the items)
AND then a `v-for` over the same list inside the slot. Each
filter row is built twice.

**Fix**: pick one. Since the template's `v-for` is the one with
the click handlers, drop the `:items` prop and keep the manual
`v-for`. (Or vice versa — but pick.)

## B11: job-tab status fetched on every expand toggle

`components/admin/tabs/job-tab.vue:124`: `@click="loadAllStatuses"`
attached to the entire expand-row container. Expanding/collapsing
the UI fires the API call.

**Fix**: move the click to a specific control inside the row, or
gate inside `loadAllStatuses` by checking expand state.

## B12: metadata-dialog setTimeout leak

`components/metadata/metadata-dialog.vue:124-138`:
`updateProgress` uses recursive `setTimeout` without storing the
timer ID; can fire after dialog unmount → null-ref errors.

**Fix**: store timer ID; clear it in `beforeUnmount`.

## B13: pager dynamic component swap leak

`components/reader/pager/pager.vue:50-60`: `<component :is="...">`
without an explicit `:key`. Vue can re-use the existing instance
if both `:is` values resolve to the same component definition,
but in this case (vertical/horizontal pager) the swap should be
a full unmount.

**Fix**: add `:key="component"`. Forces full unmount + scroll-
listener cleanup when the user toggles reading direction.

## Suggested commit shape

One PR, ~13 commits (one per bug). The 1-liner ones (B1, B2, B6,
B8) are close to no-risk. The race-fixes (B3, B4, B5, B7) need
care — verify no test depends on the prior racy behavior.

Total: ~150 LOC. Frontend-only. No backend change needed.

## Test plan

- B1: open a slow-loading page in the reader; verify the
  spinner appears after `PROGRESS_DELAY_MS`.
- B2: trigger the no-arcs case (book with no arcs metadata);
  verify the mtime API returns 200 with the new payload shape.
- B3: simulate a network blip mid-page-change; verify the
  bookmark eventually persists once connectivity returns.
- B4 / B5: rapid-click "Next Book" / different groups; verify
  the final landing state matches the last click.
- B6: verify iOS PWA download doesn't accumulate blob URLs in
  Safari memory tools.
- B7: simulate slow logout; verify no protected-route flash.
- B8: call `getGroupDownloadURL`; verify the caller's `settings`
  object is unchanged.
- B9: open the search combobox 50 times; verify history caps at
  10.
- B10: visually inspect the filter sub-menu; verify each row
  appears once.
- B11: expand/collapse a job row; verify no API call fires.
- B12: open and close the metadata dialog rapidly; verify no
  console errors about null refs.
- B13: switch reader from vertical to horizontal and back;
  verify scroll listener count is stable (devtools event
  listeners panel).
