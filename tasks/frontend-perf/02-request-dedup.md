# 02 — Request dedup, AbortController, WS backoff

Network thrash. Each item is a few lines on the right
abstraction; the whole sub-plan is ~200 LOC.

## A — `useAbortableAction` helper for navigation-driven endpoints

The browser store and reader store fire API calls from actions
that the user can re-trigger by rapid clicks (group switch, book
switch, page nav). Without an AbortController, late responses
overwrite the current state with stale data.

Add a small helper used by the affected actions:

```js
// stores/util/abortable.js
const _controllers = new Map();

export function useAbortable(key) {
  const prev = _controllers.get(key);
  if (prev) prev.abort();
  const controller = new AbortController();
  _controllers.set(key, controller);
  return controller.signal;
}
```

Sites that adopt it:

- `stores/browser.js:562-601` `loadBrowserPage` (B5)
- `stores/reader.js:413-475` `loadBooks` (B4)
- `stores/browser.js:629-645` `loadMtimes`
- `stores/browser.js:620-626` `loadFilterChoices`

Each passes the signal through xior's `signal` option.
Aborted requests should not call `$patch`; xior throws
`AbortError`, suppress it.

## B — Pending-promise dedup for read-only fetches

For endpoints where multiple callers want the same result fast
(notably `mtime` checks), a pending-promise cache eliminates
duplicate in-flight requests:

```js
const _pending = new Map();

async function dedupedFetch(key, fetcher) {
  if (_pending.has(key)) return _pending.get(key);
  const p = fetcher().finally(() => _pending.delete(key));
  _pending.set(key, p);
  return p;
}
```

Sites:

- `stores/browser.js:629-645` `loadMtimes` (N1)
- `stores/socket.js:125-142` cross-store mtime fan-out (N8)
  — both browser and reader try to fetch on the same socket
  notification; share the result.

## C — WebSocket exponential backoff

`stores/socket.js:20-21`:

```js
const RECONNECT_DELAY_MS = 3_000;  // fixed
const RECONNECT_RETRIES = Infinity;
```

**Fix**: exponential with cap. 1s, 2s, 4s, 8s, 16s, 30s (cap).
Reset on successful connect.

```js
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

function nextDelay(attempts) {
  return Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** attempts);
}
```

## D — CSRF token cache

`api/v3/base.js:13-23`: regex-extract from `document.cookie` per
request. Cache it.

```js
let _cachedToken;
function getCsrfToken() {
  if (_cachedToken !== undefined) return _cachedToken;
  _cachedToken = parseFromCookie();
  return _cachedToken;
}
```

Invalidate on observed CSRF 403 (the existing handler at
`base.js:29-44` already deletes `sessionid` — also clear
`_cachedToken` there).

## E — Admin static-table cache

`api/v3/admin.js:10,35,39`: every `getAll*` call appends a `ts`
timestamp param via `serializeParams`, defeating any HTTP-cache
benefit.

For the genuinely-static endpoints (`getAgeRatingMetrons`,
choices) drop the `ts` param. For dynamic ones (users, libraries,
flags) keep it but add a 5-second sticky cache at the store level
so a tab swap doesn't refetch.

## F — Admin loadTables Promise.all

`stores/admin.js:107-111`: fires multiple `loadTable` calls
without awaiting. Race-prone.

**Fix**: `await Promise.all(tables.map(t => this.loadTable(t)))`.

## G — admin loadAllStatuses incremental update

`stores/admin.js:197-211`: rebuilds the entire status map per
call. For the job-tab live-updating UI this thrashes Pinia
subscribers.

**Fix**: diff the response against state; only `$patch` what
actually changed.

## H — OPDS URL pre-fetch on bootstrap

`api/v3/common.js:86-96`: `loadOPDSURLs` populates lazily; first
caller blocks on the network.

**Fix**: in `app.vue`'s `created` (or wherever `loadProfile()` is
called), fire `loadOPDSURLs()` in parallel via
`Promise.allSettled`. Don't block boot on its result.

## I — Single setTimezone path

`app.vue:29-33`: `created` chains `loadProfile().then(setTimezone)`;
a watcher on `user` also calls `setTimezone`. Both fire on first
load.

**Fix**: drop the `created` chain; rely on the watcher with
`immediate: true`.

## J — CSRF 403 user surfacing

`api/v3/base.js:29-44`: clears `sessionid` on CSRF 403 but
doesn't tell the user. Subsequent API calls 401, page silently
breaks.

**Fix**: dispatch a notification through `useCommonStore`'s
form-error machinery — "Session expired, please reload."

## Correctness invariants

- **Aborted requests must not crash**: xior throws `AbortError`;
  catch and suppress. Never `$patch` from an aborted request.
- **Pending-promise cache must clear on settle**: `.finally`
  removes the key. A stuck in-flight request would otherwise
  pin the dedup forever.
- **WS backoff reset on connect**: don't carry the attempt
  counter across a successful connection cycle.
- **CSRF cache eviction on 403**: covered above; needed because
  Django rotates the token on auth state changes.

## Risks

- **AbortController on iOS Safari < 16.4**: `fetch(url, { signal })`
  works but the abort behavior on certain xhr-fallback paths is
  flaky. Guard the abort suppression broadly: catch any error
  whose `name === "CanceledError" || name === "AbortError"` and
  suppress. xior wraps these consistently.
- **Pending-promise cache on stale results**: if a fetcher
  closure captures stale state, the cached promise serves stale
  data. Keep cache scoped per-route or per-key, not global.
- **Exponential backoff on flaky networks**: a 30s cap is fine
  for codex's use case (the librarian heartbeats already drive
  manual refresh). Don't go higher without measuring.

## Suggested commit shape

One PR, several commits — one per concern (A, B, C, D, E, F, G,
H, I, J). The shared helpers (`useAbortable`, `dedupedFetch`)
land first as plumbing; subsequent commits adopt them.

Total ~200 LOC.

## Test plan

- A: rapid group-switch test fires 5 `loadBrowserPage` calls in
  100ms; assert only the last one's payload reaches state.
- B: simulate two callers requesting `loadMtimes` at the same
  time; assert one network request fires.
- C: kill the WS server, observe the client's reconnect cadence
  (1s, 2s, 4s, ...).
- D: verify the CSRF token regex runs once across 10 requests.
- E: verify `getAgeRatingMetrons` doesn't include `ts=...`.
- F: assert `loadTables` resolves only after all loaded.
- G: assert `loadAllStatuses` only `$patch`es changed keys.
- H: time first-time `loadOPDSURLs` callers vs. baseline; verify
  the cache is warm.
- I: verify `setTimezone` fires once per user-change, not twice.
- J: simulate CSRF 403; verify the toast appears.
