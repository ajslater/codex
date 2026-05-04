# Stage 2 — Reader route caching + settings name-lookup batching

Closes Phase D from
[99-summary.md §3](99-summary.md#3-suggested-landing-order):

- **Tier 1 #3** — re-enable route caching on `c/<pk>` with
  `cache_page(READER_TIMEOUT)` + `vary_on_cookie`. Mirrors OPDS
  Stage 2.
- **Tier 2 #7** — fold the per-scope name lookup in the settings
  GET into the comic prefetch via `select_related`.

## Headline

Warm pass for the reader endpoint drops to **0 queries / ~1.9 ms**
(cache hit, response replayed without entering the view layer).
Cold pass is unchanged — the view still runs the full pipeline on a
cache miss.

| Flow                  | Cold queries (before → after) | Warm queries (before → after) | Warm wall (before → after) |
| --------------------- | ----------------------------: | ----------------------------: | -------------------------: |
| **reader_open**       |                       25 → 25 |                    **24 → 0** |   **36 → 1.9 ms (-94%)**   |
| **reader_open_large** |                       25 → 25 |                    **24 → 0** |   **35 → 1.9 ms (-95%)**   |
| **settings_multiscope** |                  **8 → 7**  |                         7 → 6 |       8 → 8 ms (noise)     |
| settings_global       |                         4 → 4 |                         3 → 3 |              5 → 5 ms      |
| (page_* flows)        |              within ±0 noise |               within ±0 noise |     uncached, by design    |

Real-world reader traffic is dominated by tab refreshes / mobile-app
re-foreground patterns where the same `c/<pk>` URL gets hit in
quick succession — those collapse to the warm path now.

Artifacts: `tasks/reader-views-perf/stage2-before.json` and
`stage2-after.json`.

## What landed

### #3 — `cache_page(READER_TIMEOUT)` + `vary_on_cookie` on `c/<pk>`

`codex/urls/api/reader.py`. Added a new `READER_TIMEOUT = 60`
constant in `codex/urls/const.py` (mirrors `OPDS_TIMEOUT` shape and
TTL trade-off).

```python
path(
    "<int:pk>",
    cache_page(READER_TIMEOUT)(vary_on_cookie(ReaderView.as_view())),
    name="reader",
),
```

`vary_on_cookie` adds `Vary: Cookie` to the response BEFORE
`cache_page`'s `process_response` stores it, so the cache key
includes the session cookie — different users with different
sessions get separate cache entries. This is the same composition
the cover endpoint already uses.

The reader endpoint serves per-user state (bookmark page,
per-comic settings, arc context). The 60 s TTL trade-off:

- **Win:** the cold pipeline (25 cold queries / ~50 ms) drops to a
  cache lookup (~1.9 ms) on every hit within 60 s of the first.
- **Cost:** if a librarian-driven Comic update lands within 60 s
  of a reader open, the next reader open returns stale `mtime`
  for up to 60 s. Bookmark / per-comic settings changes made
  within the cache window also surface stale until expiry.
- **Net:** acceptable for the reader endpoint. The page endpoint
  (`c/<pk>/<page>/page.jpg`) which writes bookmark progress
  remains uncached server-side, so progress writes still hit the
  DB synchronously.

The page binary, settings, and download routes remain unchanged —
only the reader endpoint is wrapped.

### Cross-user cache isolation verified

Manual smoke test against two users with different ACLs:

- User A (staff/superuser) hits `/api/v3/c/10785` cold → 762 B.
- User A warm → 762 B (cache hit, identical content).
- User B (non-staff) hits same URL cold → **739 B** (smaller payload
  due to ACL-filtered arcs).
- User B warm → 739 B (cache hit on B's session, no leakage from A).
- `Vary: Accept, Cookie, origin` confirmed on every response.

### #7 — Fold per-scope name lookup into comic prefetch

`codex/views/reader/settings.py`. The settings GET handler
prefetches the comic to resolve scope FK values (e.g. `series_id`,
`parent_folder_id`). Added `select_related` for the related models
keyed off a new `_COMIC_FK_TO_RELATED` map:

```python
_COMIC_FK_TO_RELATED = MappingProxyType({
    "series_id": ("series", "name"),
    "parent_folder_id": ("parent_folder", "name"),
})
```

The comic prefetch now joins `codex_series` / `codex_folder` and
the new `_resolve_scope_name` helper reads the display name off
`comic.series.name` / `comic.parent_folder.name` — no extra
query.

Story-arc scope (`a`) takes its `scope_pk` from a `?story_arc_pk=`
query param (not from the comic's FK pyramid), so the helper
falls back to the targeted `Model.objects.filter(pk).values_list("name")`
lookup when the comic prefetch can't help. That fallback only
fires when the `a` scope is requested AND the user's frontend
provides the story_arc_pk.

`settings_multiscope` (`?scopes=g,s,c`) drops 8 → 7 cold queries.
On a hypothetical `?scopes=g,s,f,a,c` request, the savings would
be 2 (one for series, one for folder; story_arc still costs 1).

## Verification

- **`make test`** — 24 / 24 pass.
- **`make lint`** + **`make typecheck`** — Python clean.
- **Cross-user isolation smoke test** — User A and User B see
  different payloads on the same URL; warm hits return their own
  cached response with no leakage.
- **Settings spot-check** — `?scopes=g,s,c` returns
  `scope_info.s.name = "JLA/Avengers"` (correct series name from
  the joined row); silk SQL trace confirms only 1 codex_comic
  query that JOINs codex_series, no separate Series.objects query.
- **Harness re-run** — stage2-after.json reproducible across runs.

## Open monitoring items

- **Cache invalidation on librarian-driven library updates.** The
  60 s TTL bounds staleness but isn't zero. If users report
  "bookmark progress doesn't update on the reader sidebar", the
  fix is either (a) shorten `READER_TIMEOUT`, or (b) wire a
  `post_save` signal on `Comic` / `Bookmark` that clears the
  cached entries. Same posture as OPDS Stage 2's monitoring item.
- **Cache disk pressure.** Reader response bytes are small (~700 B
  per response) compared to cover responses (100s of KB). Cache
  pressure is negligible; the default `MAX_ENTRIES = 10000` bound
  is plenty.

## What's next

- **Phase E** — Tier 1 #1 (Comicbox archive cache for the page
  endpoint). Highest-risk; needs production traffic data before
  scheduling.
- **Phase F** — Tier 3-4 cleanups (#8, #11, #12, #15).
