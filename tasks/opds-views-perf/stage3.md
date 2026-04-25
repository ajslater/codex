# Stage 3 — Preview pipeline cache sharing + OPDS book queryset joins

Closes [Tier 1 #4](99-summary.md#2-ranked-backlog) (preview-pipeline
re-runs) plus the related sub-plan 02 #3 / Tier 4 #17
(`select_related` shortfall on the OPDS book queryset).

## Headline

`v2_start`: **53 → 29 cold queries (-24, ~45% reduction)**.

| Flow                    | Cold queries (before → after) | Notes                              |
| ----------------------- | ----------------------------: | ---------------------------------- |
| **v2_start**            |                  **53 → 29** | -15 volume + -9 library shared    |
| v2_manifest             |                       24 → 23 | -1 volume FK on the single comic   |
| (other 9 flows)         |              within ±0 noise | unaffected                         |

Wall-time noise dominates the cold-pass timing on this dev DB / cold
silk-instrumented harness. Query-count is the trustworthy metric.

Artifacts:

- `tasks/opds-views-perf/stage3-before.json` — captured against
  post-Stage-2 HEAD.
- `tasks/opds-views-perf/stage3-after.json` — captured with both
  fixes applied.

## Profiling — what the 51 cold queries actually were

Pre-fix silk SQL trace on `/opds/v2.0` (cold):

| Count | Table                | Notes                                         |
| ----: | -------------------- | --------------------------------------------- |
|    15 | `codex_volume`       | Per-publication FK lookup (N+1 across 3 previews × 5 pubs) |
|    12 | `codex_library`      | ACL filter rerun per preview pipeline (4 each × 3 previews) |
|     9 | `codex_comic`        | Filter / annotation queries — preserved      |
|     6 | `codex_adminflag`    | Admin flag fan-out (mix of fresh fetches and age-rating join queries) |
|     4 | `codex_userauth`     | Auth ACL pipeline (preserved)                 |
|     3 | misc.                | Session / user / publisher / settings        |

The 15 volume queries and 9 of the 12 library queries are the
fan-out targets. Both come from the preview pipeline running 3 full
filter / annotation / iteration passes (one per `PREVIEW_GROUPS`
link spec — Keep Reading / Latest Unread / Oldest Unread).

## What landed

### 1. `OPDS2FeedLinksView.get_book_qs` — `select_related("volume", "language")`

`codex/views/opds/v2/feed/feed_links.py`. Added an `@override`
that augments the parent `BrowserView.get_book_qs` result:

```python
@override
def get_book_qs(self) -> tuple:
    book_qs, book_count, zero_pad = super().get_book_qs()
    if book_count:
        book_qs = book_qs.select_related("volume", "language")
    return book_qs, book_count, zero_pad
```

The base `BrowserView.get_book_qs` joins `series` only, with an
explicit comment noting that `volume` "isn't needed for OPDS." That
comment is wrong:

- `Comic.get_title(obj, volume=True, ...)` reads `obj.volume.name`
  and `obj.volume.number_to` per publication.
- `_publication_metadata` reads `obj.language.name` per publication
  when the language FK is set.

Without these joins, every publication iteration fired one lazy
`Volume.objects.get(pk=...)` and one lazy `Language.objects.get(pk=...)`
query. On the start page (3 previews × 5 publications each), that's
15 N+1 volume queries — the largest single contributor to the cold
v2_start cost.

The override is on `OPDS2FeedLinksView` (the lowest shared ancestor
of both `OPDS2FeedView` and the preview-instantiated
`OPDS2FeedLinksView()`), so every OPDS v2 path that calls
`get_book_qs` benefits — including the manifest path and any future
v2 view added below this class. v1 already has its own
`select_related("series", "volume", "language")` in
`v1/facets.py:64`; this brings v2 to parity.

### 2. Share request-scoped caches with the preview feed_view

`codex/views/opds/v2/feed/publications.py:_get_publications_preview_feed_view`.
Each `PREVIEW_GROUPS` link spec instantiates a fresh
`OPDS2FeedLinksView()`. The new view starts with:

- `_admin_flags = None` — the AdminFlag fetch fires on first access.
- `_cached_visible_library_pks = None` — the visible-library ACL
  computation fires on first access.

Both depend on `(user, request)` only, **not on params/kwargs** — so
they're safe to share across all 3 preview iterations within the
same request. The fix:

```python
feed_view = OPDS2FeedLinksView()
feed_view.request = self.request
feed_view._admin_flags = self.admin_flags
feed_view._cached_visible_library_pks = self._cached_visible_library_pks
```

Pre-fix: 12 library queries (4 per preview × 3 previews) — 9 of
those are the visible-library lookup re-firing per preview.
Post-fix: 3 library queries total (the parent view's first lookup
plus residual ACL pipeline queries).

The remaining 6 admin-flag queries (mostly age-rating-with-metadata
joins fired by the bookmark filter pipeline) aren't reduced by this
fix — those are part of the per-pipeline run cost, separate
optimization opportunity. Documented as out-of-scope below.

### Out-of-scope hotspots still visible in the trace

Listed for the next operator's benefit — none are part of this PR:

- **Per-preview age-rating filter rerun** (4 codex_adminflag JOIN
  ageratingmetron queries). Each preview fires the bookmark filter
  pipeline, which runs the age-rating JOIN. Sharing the preview
  view's params-derived caches would help here, but params do
  differ across previews so the shared-cache shape used here is
  insufficient. Likely needs the bigger "single annotated queryset
  + Python-side partition" rewrite the plan flagged as the
  alternative for #4.
- **Volume FK on non-preview publication paths.** Stage 3 handles
  this via the `OPDS2FeedLinksView.get_book_qs` override. Verify
  with `harness` by exercising a folder feed or a filtered series
  feed that returns ≥10 publications — the v2_series_publications
  baseline doesn't hit this consistently due to the perf-user
  state artifact documented in `stage0.md`.

## Verification

- **`make test`** — 24 / 24 pass.
- **`make lint`** — Python lint passes; pre-existing remark warning
  on plan markdown reproduces unchanged.
- **SQL trace post-fix** — `/opds/v2.0` cold: `codex_volume = 0`
  queries (was 15), `codex_library = 3` (was 12). Total 27 queries
  (silk count; harness reports 29 due to 2 in-harness queries
  bracketing the request). Both consistent with the saved-query
  math.
- **Functional spot-check** — start-page payload structure
  unchanged: same 3 preview groups, same publications per group,
  same metadata structure. Verified via `len(content)` consistency
  across runs and visual inspection of the JSON.

## What's next

- **Phase E** — Tier 2 #7 (v1 acquisition M2M batch) and #8
  (progression PUT conditional update). Both independent and
  mechanical.
- **Phase F** — Tier 3-4 cleanups (#10 reading-order URL templating,
  #11 filters JSON memoize, #14 URL template cache, #16 manifest
  parent_folder select_related verification).
