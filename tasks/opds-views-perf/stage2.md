# Stage 2 — OPDS route caching re-enabled

Closes [Tier 1 #1](99-summary.md#2-ranked-backlog) — the highest-impact
item in the entire plan. `OPDS_TIMEOUT` flips from `0` (cache_page
no-op) to `60` (one minute), and every feed / manifest / start /
opensearch route gains `vary_on_headers("Cookie", "Authorization")`
so per-user feeds don't leak across users / auth schemes.

## Headline

Warm pass for every cacheable route drops to **0 queries / ~1.5–2.7
ms** — the cache returns the response without ever entering the view
layer. Cold pass is unchanged.

| Flow                         | Cold queries (before → after) | Warm queries (before → after) | Warm wall (before → after) |
| ---------------------------- | ----------------------------: | ----------------------------: | -------------------------: |
| v1_start                     |                       14 → 14 |                         5 → 0 |        12 → 1.7 ms (-10ms) |
| v1_root_browse               |                       15 → 15 |                        13 → 0 |        40 → 1.7 ms (-39ms) |
| v1_series_acquisition        |                       18 → 18 |                        14 → 0 |        24 → 2.7 ms (-21ms) |
| v1_acquisition_with_metadata |                       16 → 16 |                        14 → 0 |        24 → 2.0 ms (-22ms) |
| v1_opensearch                |                         3 → 3 |                         2 → 0 |          3 → 1.9 ms (-1ms) |
| v2_start                     |                       53 → 53 |                        44 → 0 |       59 → 1.8 ms (-57ms!) |
| v2_root_browse               |                       15 → 15 |                        13 → 0 |        28 → 2.4 ms (-26ms) |
| v2_series_publications       |                       18 → 18 |                        14 → 0 |        26 → 1.7 ms (-24ms) |
| v2_manifest                  |                       24 → 24 |                        21 → 0 |       62 → 2.4 ms (-60ms!) |
| v2_progression_get           |                         9 → 9 |                         8 → 8 |     10 → 10 ms (uncached, by design) |
| auth_doc_v1                  |                         2 → 2 |                         0 → 0 |             2 → 1.8 ms     |

The cold pass continues to run the full pipeline (cache miss = view
runs from scratch), so cold-query counts stay identical to Stage 1.
The win is **on every cache hit** — which in real-world OPDS traffic
is the dominant case (clients poll the same URLs repeatedly within
the cache window).

Artifacts:

- `tasks/opds-views-perf/stage2-before.json` — captured against
  post-Stage-1 HEAD with `OPDS_TIMEOUT = 0`.
- `tasks/opds-views-perf/stage2-after.json` — captured with caching
  enabled and verified.

## What landed

### `OPDS_TIMEOUT = 60` — `codex/urls/const.py`

The constant flipped from `0` (cache_page no-op) to `60`, with an
inline comment explaining the trade-off: long enough to amortize a
full feed pipeline run across a tab refresh / reader-app re-fetch,
short enough that bookmark-position changes show up before the next
poll. The disable rationale is documented in
[`stage0.md` § R1](stage0.md#r1--opds_timeout--0-rationale).

### `opds_cached(view)` helper — `codex/urls/opds/__init__.py`

A single-purpose helper that wraps a view in
`cache_page(OPDS_TIMEOUT)` + `vary_on_headers("Cookie",
"Authorization")`:

```python
def opds_cached(view):
    return cache_page(OPDS_TIMEOUT)(
        vary_on_headers("Cookie", "Authorization")(view)
    )
```

`Cookie` covers Session auth (Django's `SessionMiddleware` doesn't
auto-add `Vary: Cookie` unless the session is accessed; explicit
declaration is safer). `Authorization` covers Basic + Bearer tokens.
Without it, the same URL hit by two users with different
`Authorization` headers would return one user's response to the other
— a security bug. Mirrors the binary cover-route composition at
`codex/urls/opds/binary.py:34-38`.

### `v1.py`, `v2.py`, `root.py` — `opds_cached(...)` applied uniformly

- `codex/urls/opds/v1.py` — feed / opensearch / start.
- `codex/urls/opds/v2.py` — manifest / feed / start.
- `codex/urls/opds/root.py` — the no-trailing-slash `/opds/v2.0`
  start variant. Previously bypassed `cache_page` entirely; now
  matches `/opds/v2.0/` (trailing-slash, included from `v2.py`).

### Progression route — explicitly NOT cached

`codex/urls/opds/v2.py` previously wrapped progression in
`cache_page(0)` (no-op). The wrap is now removed. Rationale:

- Progression GET returns the user's bookmark position for a comic.
- A PUT mutates the bookmark; a GET within a 60 s cache window after
  a PUT would return the pre-PUT position.
- Multi-device sync is the worst case: device A PUTs page 100,
  device B GETs within 60 s and sees pre-PUT position. The reader
  opens the comic at the wrong page.
- `cache_page` only intercepts GET / HEAD with status 200, so PUTs
  pass through — but the asymmetry creates the staleness window.
- The ~9-query / 14 ms cold cost is small compared to the freshness
  cost.

## Verification

- **Cross-user isolation smoke test** (run via the Django test
  client):
  - User A (staff/superuser) hits `/opds/v2.0/r/0/1` cold → 16 223 B.
  - User A warm → 16 223 B (same).
  - User B (non-staff) hits same URL cold → 15 217 B (different
    payload reflecting different ACL).
  - User B warm → 15 217 B (same as B's cold, no leakage from A).
  - Confirmed `Vary: Accept, Cookie, Authorization, origin` on every
    response.
- **Progression PUT-then-GET** still returns fresh data (route is
  not wrapped).
- **`make test`** — 24 / 24 pass.
- **`make lint`** — Python lint passes; pre-existing remark warning
  on plan markdown files reproduces unchanged.
- **Harness re-run** — stage2-after.json reproducible across two
  back-to-back captures.

## Out of scope (Phase D #4)

The plan pairs Tier 1 #1 with Tier 1 #4 (start-page preview pipeline
batching). Once #1 is in place, the preview pipeline runs at most
once per cache window per user — the per-spec re-run cost is
amortized. #4 still has value (cold paths still pay the cost), but
the urgency drops dramatically. Deferring #4 to a follow-up Stage.

## Open questions / monitoring

- **Cache invalidation on library updates.** The librarian daemon's
  `Comic.save` / `Library.save` paths don't currently signal
  `cache_page` invalidation. With a 60 s TTL the staleness window is
  bounded but not zero. If user reports indicate "newly imported
  comics don't show up immediately on my OPDS client", consider
  either (a) shortening `OPDS_TIMEOUT` further, or (b) wiring a
  `post_save` signal on `Comic` / `Library` that calls
  `cache.delete_pattern("views.decorators.cache.cache_page.opds.*")`
  or equivalent.
- **Cache size bound.** `MAX_ENTRIES = 10000` in the default cache
  config (`codex/settings/__init__.py:512`). OPDS adds N entries per
  user per cached URL; back-of-the-envelope a 100-user instance with
  10 unique feed URLs each = 1 000 entries. Well within bound.
- **Per-route hit distribution.** Plan R3. Determines whether to
  push `OPDS_TIMEOUT` higher for shallow routes (catalog start) and
  lower for deep routes (acquisition feeds). Left for follow-up.

## What's next

- Phase D #4 — start-page preview pipeline batching (Tier 1 #4).
  Now that #1 is in, the per-request hit cost is amortized; #4
  remains valuable for cold paths.
- Phase E — Tier 2 #7 (v1 acquisition M2M batch) and #8 (progression
  PUT conditional update). Both independent and mechanical.
- Phase F — Tier 3-4 cleanups.
