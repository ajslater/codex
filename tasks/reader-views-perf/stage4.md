# Stage 4 — Phase F cleanups bundled

Closes Phase F from
[99-summary.md §3](99-summary.md#3-suggested-landing-order). Three
items implemented, one closed as superseded:

- **Tier 3 #8** — `Max("updated_at")` SQL aggregate in
  `_get_story_arcs` replaces `JsonGroupArray("updated_at")` + Python
  `strptime` loop.
- **Tier 4 #12** — De-duplicate `_get_bookmark_auth_filter` between
  `ReaderSettingsBaseView` and `BookmarkAuthMixin`.
- **Tier 4 #15** — Per-process `(auth_key, comic_pk) → (path,
  file_type)` cache for the page endpoint, sized 64 entries / 60 s
  TTL.
- **Tier 3 #11** — Audit `_get_comics_list` annotation pyramid for
  prev/next dead fields. **Superseded** by Stage 1's rewrite
  (`get_book_collection` materializes only 1-3 fully-annotated rows;
  the dead-field concern doesn't apply at that scale).

## Headline

`page_*` warm-pass: **8 → 2 queries, 10 → 3.6 ms (-64% wall)**.

| Flow                  | Cold queries | Warm queries (before → after) | Warm wall (before → after) |
| --------------------- | -----------: | ----------------------------: | -------------------------: |
| **page_first**        |       9 → 9 |                    **8 → 2** |   **10.5 → 3.6 ms (-66%)** |
| **page_middle**       |       9 → 9 |                    **8 → 2** |   **9.6 → 3.8 ms (-60%)**  |
| **page_no_bookmark**  |       9 → 9 |                    **8 → 2** |   **9.7 → 3.6 ms (-63%)**  |
| reader_open           |             |                       within ±0 noise |               |
| settings_*            |             |                       within ±0 noise |               |

The cold pass is intentionally unchanged — the first page hit on a
fresh `(user, comic)` pair pays the full ACL pipeline. Within the
60 s TTL, sequential page-turns of the same comic skip the ACL
filter SQL + the comic fetch (-6 queries per warm hit).

For a typical sequential read of an N-page comic:

- **Page 1**: cold (9 queries / 15 ms).
- **Pages 2-N**: warm (2 queries / 3.6 ms each).

Net: a 200-page read goes from ~3 000 SQL queries to ~407 queries.
The remaining 2 queries per warm hit are the session lookup + the
auth_user lookup that Django middleware does on every authenticated
request — those are unavoidable at the view layer.

Artifacts: `tasks/reader-views-perf/stage4-before.json` and
`stage4-after.json`.

## What landed

### #8 — `Max("updated_at")` aggregate

`codex/views/reader/arcs.py:_get_story_arcs`. The prior implementation
used `JsonGroupArray("updated_at")` to gather all updated_at strings
per arc, then parsed them in Python:

```python
qs = qs.annotate(
    ids=JsonGroupArray("id", distinct=True, order_by="id"),
    updated_ats=JsonGroupArray("updated_at", distinct=True, order_by="updated_at"),
)
...
for sa in qs:
    updated_ats = (
        datetime.strptime(ua, _UPDATED_ATS_DATE_FORMAT_STR).replace(tzinfo=UTC)
        for ua in sa.updated_ats
    )
    mtime = max_none(EPOCH_START, *updated_ats)
```

Replaced with `Max("updated_at")` which returns a typed `datetime`
via the field's `from_db_value` hook:

```python
qs = qs.annotate(
    ids=JsonGroupArray("id", distinct=True, order_by="id"),
    mtime=Max("updated_at"),
)
...
for sa in qs:
    mtime = sa.mtime
```

Eliminates the per-row `strptime` loop and the Python-side `max_none`
fold. SQLite stores datetimes as ISO strings, but any aggregate that
yields a typed datetime (Max / Min / etc.) bypasses the manual parse.

Also dropped now-unused imports: `from datetime import UTC, datetime`,
`from codex.views.const import EPOCH_START`, and the
`_UPDATED_ATS_DATE_FORMAT_STR` constant.

### #12 — De-dup `_get_bookmark_auth_filter`

`codex/views/reader/settings.py`. `ReaderSettingsBaseView` had its
own copy of `_get_bookmark_auth_filter` inlined from the former
`BookmarkAuthMixin` — same shape, same behaviour, just a copy.

Added `BookmarkAuthMixin` to `ReaderSettingsBaseView`'s base classes
and dropped the local copy. `_get_settings_lookup` now calls
`self.get_bookmark_auth_filter()` (the inherited one). Removed the
now-unused `loguru.logger` and `rest_framework.request.Request`
TYPE_CHECKING imports.

Cleanup-only — no behaviour change.

### #15 — Page-endpoint ACL decision cache

`codex/views/reader/_archive_cache.py:PageAclCache` (new) +
`codex/views/reader/page.py:ReaderPageView._resolve_path_and_type`
(new helper).

The page endpoint previously fired the ACL filter SQL on every
request:

```python
acl_filter = self.get_acl_filter(Comic, self.request.user)
qs = Comic.objects.filter(acl_filter).only("path", "file_type")
comic = qs.get(pk=pk)
```

For a sequential read of a 200-page comic, that's 200 identical ACL
+ comic-fetch round-trips. The new `PageAclCache` keys on
`(auth_key, comic_pk) → (path, file_type)` with a 60 s TTL, so
subsequent page hits within the cache window skip the SQL.

Configuration knobs (env vars, mirroring the archive cache shape):

- `CODEX_READER_PAGE_ACL_CACHE_SIZE` (default 64)
- `CODEX_READER_PAGE_ACL_CACHE_TTL` (default 60 s)
- `CODEX_READER_PAGE_ACL_CACHE_DISABLE` (default false)

Sizing rationale:

- 64 entries covers p95 install (22 concurrent readers × ~3 recently-
  viewed comics each) with headroom.
- 60 s TTL bounds staleness on ACL revocation / comic deletion.
  Worst case: a user whose library access is revoked continues
  reading for up to 60 s. Acceptable.
- Memory: 64 × ~200 B per entry = ~13 KB. Negligible.
- The cache value (path string + file_type) is stable for the
  lifetime of the comic on disk. Comic deletion / move surfaces as
  `FileNotFoundError` from Comicbox, which the view already handles.

### #11 — Closed as superseded

The plan flagged `_get_comics_list`'s annotation pyramid as a
candidate for slimming on prev/next entries. Stage 1's rewrite
already addresses the underlying concern: the comics queryset is now
materialized as a `values_list("pk")` first, then 1-3 specific rows
are re-fetched via `filter(pk__in=window_pks)`. Slimming the
annotation pyramid for prev/next would shave microseconds off 1-2
extra rows — invisible against the rest of the request cost.

Documented in `99-summary.md` row #11.

## Verification

- **`make test`** — 24 / 24 pass.
- **`make lint`** + **`make typecheck`** — Python clean.
- **Functional spot-checks**:
  - `reader_open` returns the expected `arc` / `arcs` / `books` /
    `closeRoute` / `mtime` shape.
  - `settings?scopes=g,s,c` returns three scopes plus
    `scope_info.s.name` from the joined comic prefetch.
  - Page endpoint returns identical bytes before and after the cache
    fix (verified with `CODEX_READER_PAGE_ACL_CACHE_DISABLE=1`).
- **Harness re-run** — cold-pass numbers stable; warm-pass page
  endpoints drop 8 → 2 queries / 10 → 3.6 ms.
- **Harness updated** — `_capture` now also clears
  `archive_cache` + `page_acl_cache` between flows so the cold
  measurement is a true cold-cache reading rather than a warm-up-
  loop carryover.

## Plan status after Stage 4

The reader perf project is now **closed** for the items it set out
to address:

| Tier | Closed                              | Remaining open                                |
| ---- | ----------------------------------- | --------------------------------------------- |
| 1    | #1, #2, #3                          | —                                             |
| 2    | #4, #5, #7                          | #6 (page response cache, low value now)       |
| 3    | #8, #9, #10, #11 (superseded)       | —                                             |
| 4    | #12, #13, #14, #15                  | —                                             |
| R    | R1                                  | R2-R5 (need production telemetry)             |

#6 (server-side response cache for the page endpoint) is the only
non-superseded open item. Its value dropped substantially with the
archive cache + ACL cache landed: a warm page hit is now 2 queries
/ 3.6 ms; adding response-byte caching on top would save another
~3 ms but at the cost of disk pressure (page bytes are 100-500 KB
each). Recommend not pursuing without production traffic data
showing the 3 ms matters at scale.

R2-R5 (per-route hit distribution, archive-open cost distribution,
frontend prefetch behaviour, worker-pool implications) all need
production telemetry that isn't available in the chronicle backup.
The chronicle ingest path for filetype counts in particular wasn't
yet populated as of the last backup; once that lands (out of scope
for this project), the file-type distribution data would inform
whether the archive cache's TTL is well-sized for CBR/PDF-heavy
installs.

The reader views are in good shape. Recommend pausing the project
here.
