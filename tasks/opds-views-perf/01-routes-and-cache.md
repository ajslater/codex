# 01 — Routes and cache topology

OPDS-specific routing decisions and the cache decorator wrapping. The
single highest-impact item in this entire plan lives here:
`OPDS_TIMEOUT = 0` makes every `cache_page` wrap on every OPDS feed
route a no-op.

## Files in scope

| File                                       | LOC | Purpose                                               |
| ------------------------------------------ | --- | ----------------------------------------------------- |
| `codex/urls/const.py`                      | 7   | Cache TTL constants                                   |
| `codex/urls/opds/root.py`                  | 29  | Top-level OPDS routing + version redirects            |
| `codex/urls/opds/v1.py`                    | 33  | v1 feed routes (Atom XML)                             |
| `codex/urls/opds/v2.py`                    | 40  | v2 feed routes (JSON-LD), manifest, progression       |
| `codex/urls/opds/binary.py`                | 57  | Cover / page / download routes                        |
| `codex/urls/opds/authentication.py`        | —   | Auth doc route                                        |
| `codex/views/opds/feed.py`                 | 21  | `OPDSBrowserView` base — adds throttling on top of `BrowserView` |
| `codex/views/opds/auth.py`                 | 27  | Auth helper for binary endpoints                      |
| `codex/views/opds/error.py`                | 70  | Error response rendering                              |
| `codex/views/opds/settings.py`             | 17  | OPDS settings mixin                                   |
| `codex/views/opds/start.py`                | 20  | Start-page mixin (overrides `_get_group_queryset`)    |
| `codex/views/opds/user_agent.py`           | 14  | User-agent name resolution                            |
| `codex/views/opds/authentication/v1.py`    | 79  | Static auth doc view                                  |
| `codex/views/opds/opensearch/v1.py`        | 20  | Static opensearch description doc view                |
| `codex/views/opds/binary.py`               | 50  | Cover / page / download views                         |

## Hotspots

### #1 — `OPDS_TIMEOUT = 0` makes every `cache_page` wrap a no-op

`codex/urls/const.py:7`:

```python
OPDS_TIMEOUT = 0  # BROWSER_TIMEOUT
```

Every OPDS feed route in `codex/urls/opds/v1.py` and `v2.py` is
wrapped in `cache_page(OPDS_TIMEOUT)`:

- `v1.py:18` — feed route
- `v1.py:23` — opensearch
- `v1.py:29` — start
- `v2.py:19` — manifest
- `v2.py:25` — progression
- `v2.py:30` — feed
- `v2.py:35` — start

When the timeout is 0, Django's `cache_page` decorator stores nothing
and serves nothing — every wrapped view runs the full pipeline on
every request. The wrapping is dead weight today, but the comment
(`# BROWSER_TIMEOUT`) suggests it was once `60 * 5` and got disabled.

**The investigation:** Why was it disabled? The two plausible reasons
are (a) auth/cookie variance defeating the cache key, and (b) some
correctness regression nobody had time to track down. The comment
doesn't say. Until that decision is sourced — git log on
`codex/urls/const.py`, plus a scan of the OPDS issue tracker — every
other Tier 1 item in this plan is dwarfed by re-enabling caching.

**What re-enabling correctly would require:**

- A cache key that varies on `(user_id, url_path, query_params)`. The
  default `cache_page` keys on URL + Vary headers; for OPDS that
  means the response leaks across users unless `Vary: Cookie,
  Authorization` is set (the binary cover routes already do this — see
  `codex/urls/opds/binary.py:36-37`). Confirm whether the feed routes
  set those Vary headers.
- A short TTL — 60 s is plenty for an OPDS catalog. Long enough to
  collapse the per-request pipeline cost across a tab refresh; short
  enough that bookmark-position changes show up before the next poll.
- A signal-based invalidation hook on `Library.save`/`Library.delete`
  and on `Comic.save` would be ideal but isn't strictly required if
  the TTL is short.

**Severity:** the entire OPDS feed pipeline runs every request today.
Wins from #2-#10 in this plan are second-order corrections to a path
that should ideally not run for most requests.

### #2 — Binary cover routes are correctly cached

`codex/urls/opds/binary.py:34-50` wraps cover and custom-cover views
in:

```python
cache_page(COVER_MAX_AGE)(
    cache_control(max_age=COVER_MAX_AGE, public=True)(
        vary_on_headers("Cookie", "Authorization")(view)
    )
)
```

This is the correct shape for an authenticated binary cache:
`Vary: Cookie, Authorization` ensures responses don't leak across
users / auth schemes. `COVER_MAX_AGE = 60 * 60 * 24 * 7` (one week).

**No change needed.** This is the template for what the feed routes
should look like once the timeout is re-enabled.

### #3 — Page route caches via `cache_control` only, not `cache_page`

`codex/urls/opds/binary.py:23` wraps `OPDSPageView` in
`cache_control(max_age=PAGE_MAX_AGE, public=True)` but does **not**
add `cache_page`. That means the response carries client-cache
headers but the server still re-runs the view on every miss.

For OPDS reader streaming this is probably correct (pages are streamed
from disk anyway, so `cache_page` would buffer the entire page into
memcache), but verify the view body actually streams via
`FileResponse` rather than building a bytes blob.

**Severity:** low, mainly a documentation note.

### #4 — Static doc views are uncached

`codex/views/opds/authentication/v1.py` and
`codex/views/opds/opensearch/v1.py` serve static documents (auth doc
and opensearch description). Both are per-server-static — no
user-specific data, no DB queries — and both are wrapped in
`cache_page(OPDS_TIMEOUT)` which is currently a no-op.

When the timeout is set, these routes will benefit. Worth confirming
they really are static (no per-user URL resolution) before relying on
that.

**Severity:** low individually, but they're hit on every OPDS catalog
discovery so the cumulative overhead is noticeable.

### #5 — `OPDSBrowserView` adds throttling on top of `BrowserView`

`codex/views/opds/feed.py:12-15`:

```python
class OPDSBrowserView(OPDSBrowserSettingsMixin, UserActiveMixin, BrowserView):
    throttle_classes: Sequence[type[BaseThrottle]] = (ScopedRateThrottle,)
    throttle_scope = "opds"
```

`ScopedRateThrottle` runs on every request before the view executes.
The throttle key is computed from `request.user` + `throttle_scope`,
which is a cheap dict lookup on the cache backend. **Not a hotspot,**
but worth knowing it runs even when the request would otherwise be
served from cache (DRF throttles run before view dispatch, not before
URL matching). If route caching is re-enabled (#1), throttling will
still run per request — that's correct per DRF design.

### #6 — Start page resets settings on every request

`codex/views/opds/start.py:13-14`:

```python
def init_params(self) -> MutableMapping[str, Any]:
    """Hard reset settings to default just by landing on the page."""
    return self.get_browser_default_params()
```

Every hit on the OPDS start page returns default params, which is
correct semantically but means the start page can't share a cache key
with itself across users (different users have different "default"
filters). Combined with #1, this is fine — but if a Tier 1 caching
fix lands, the start page deserves its own cache layer keyed on
`(user_id, library_max_updated_at)` rather than full URL.

**Severity:** low.

## Interactions with `BrowserView`

`OPDSBrowserView` adds:

- `throttle_classes`, `throttle_scope`
- `_user_agent_name` lazy attribute
- `OPDSBrowserSettingsMixin` (different settings model than browser
  view — `SettingsOPDS` vs `SettingsBrowser`)

It does **not** override:

- `get_filtered_queryset` — full ACL + search + annotation pipeline
  fires per request unless cached upstream.
- `_get_group_and_books` — the entire annotation cascade (card,
  order, bookmark) runs.
- `_get_query_filters` — search parser, FTS5, m2m gating, all run.

In other words: every win from browser-views Stage 1-5d already flows
through. The OPDS-specific items are #1 (caching) and the per-entry /
per-publication serialization layered on top of the result (sub-plans
03 and 04).

## Other small files (orientation only)

- `error.py` (70 LOC) — exception → response rendering. No DB cost,
  no hot path.
- `auth.py` (27 LOC) — adds `OPDSAuthMixin`, applied to binary +
  progression. Pure permission checks.
- `settings.py` (17 LOC) — overrides `SettingsBrowser` to
  `SettingsOPDS`. Same diff-save concern as browser plan #8 in
  principle, but the settings write path on OPDS is far less hot
  (clients don't usually mutate settings on every request like the
  browser UI does).
- `start.py` (20 LOC) — see #6 above.
- `user_agent.py` (14 LOC) — pulls user-agent from headers and
  normalizes. Cached on view instance via property; cheap.
- `feed.py` (21 LOC) — see #5 above.

## What's worth measuring before scheduling

1. **Why is `OPDS_TIMEOUT = 0`?** — git blame, issue tracker, ask
   the maintainer. Until this is known, #1 is blocked.
2. **Cold latency for a v1 root and v2 root request.** Both should
   already be reasonable thanks to inherited browser-views wins, but
   the per-entry overhead documented in 03 and 04 may still be
   meaningful.
3. **Per-route hit distribution.** OPDS clients refresh feeds on
   different cadences; if 80 % of requests are start-page or
   single-folder root, caching the start page (only) could capture
   the bulk of the win without solving #1 in full generality.
