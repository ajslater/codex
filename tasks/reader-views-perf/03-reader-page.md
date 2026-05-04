# 03 — Reader page binary (`c/<pk>/<page>/page.jpg`)

The hottest endpoint in the codex. Returns a single page image
extracted from the comic archive (CBZ / CBR / PDF). Hit on every
page turn. Optionally records the bookmark.

## Files in scope

| File | LOC | Purpose |
| ---- | --- | ------- |
| `codex/views/reader/page.py` | 106 | `ReaderPageView`. Page extraction, content-type negotiation, async bookmark update. |
| `codex/urls/api/reader.py:21` | — | URL: `c/<pk>/<page>/page.jpg`, wrapped in `cache_control(PAGE_MAX_AGE)` only (no server-side `cache_page`). |

## Per-request cost shape

```python
def _get_page_image(self):
    acl_filter = self.get_acl_filter(Comic, self.request.user)
    qs = Comic.objects.filter(acl_filter).only("path", "file_type").distinct()
    pk = self.kwargs.get("pk")
    comic = qs.get(pk=pk)              # 1 SQL query

    page = self.kwargs.get("page")
    pdf_format = ...
    with Comicbox(comic.path, ...) as cb:
        page_image = cb.get_page_by_index(page, pdf_format=pdf_format)
        # ↑ DISK I/O: opens the archive (zip/rar/pdf), seeks to page, extracts.
    ...
    return page_image, content_type
```

Then `_update_bookmark` queues an async task (no SQL on request
thread). The page bytes come back via `HttpResponse(page_image,
content_type=...)`.

Per-request cost:

- 1 SQL query for the comic ACL/filter.
- 1 disk I/O to open the comic archive.
- Page extraction (CPU + disk read for the page bytes).
- `Vary: Cookie`-style HTTP cache headers via `cache_control`.

The Comicbox open dominates. CBZ open is fast (zip TOC read +
single-entry read); CBR open is slower (the `unrar` shell-out is
~10 ms minimum); PDF open is slowest (libpoppler init).

## Hotspots

### #1 — Comicbox opens the archive on every page request

`codex/views/reader/page.py:63-64`:

```python
with Comicbox(comic.path, config=COMICBOX_CONFIG, logger=logger) as cb:
    page_image = cb.get_page_by_index(page, pdf_format=pdf_format)
```

A 200-page comic = 200 archive opens per read-through. The browser
loads pages sequentially as the user scrolls; reader apps may
prefetch the next 1–2 pages. Either way, every page hit pays the
archive-open cost.

Mitigations:

- **Pool the open archive per (comic, request thread, short
  TTL).** A request-scoped `Comicbox` cache keyed on `comic_path`,
  with explicit close on cache eviction. The browser's page-turn
  pattern is "page N → page N+1 → page N+2", so re-opening the
  same archive 3 times in 3 seconds is wasted work. A 30-second
  per-process cache (LRU bounded) would absorb this.
  - **Risk:** memory + file-descriptor pressure if many comics
    are open simultaneously. The LRU size needs care. Worker
    pool implications: with multiple Granian workers the cache
    is per-worker, so memory multiplies.
- **Pre-extract pages in advance.** Background task generates page
  images on import; the page endpoint returns a static file. Storage
  cost. Already partly addressed by the cover pipeline; pages would
  be similar but more numerous.
- **Streaming the page from a long-lived archive handle.** Same
  shape as the pool above but explicitly per-comic.

**Severity: very high.** Page-turn perceived latency. The biggest
single win for the reader subsystem if it can be done safely.
Needs measurement of cold vs. warm archive open to scope.

### #2 — `Comic.objects.filter(acl_filter).only("path", "file_type").distinct().get(pk=pk)`

`codex/views/reader/page.py:51-54`:

```python
acl_filter = self.get_acl_filter(Comic, self.request.user)
qs = Comic.objects.filter(acl_filter).only("path", "file_type").distinct()
comic = qs.get(pk=pk)
```

The ACL filter on every page request includes the visible-libraries
sub-query. For most users this is a fast index hit; for users with
many libraries it's a join. The `.distinct()` is required because
the ACL filter joins through `library_groups`.

Mitigations:

- **Cache the (user, comic_pk) ACL decision per-process.** A small
  LRU keyed on `(user_id, comic_pk)` with a 60-second TTL would
  skip the per-page ACL check during a single read-through. Risk:
  ACL is sensitive (revoke-vs-cache); per-process caching with a
  short TTL is generally safe but worth flagging.
- **Inline the path lookup.** If the comic's `path` and `file_type`
  are known from the prior reader endpoint hit, the page endpoint
  could trust them via signed query parameters. More complexity,
  not a real win unless the ACL query proves expensive.

**Severity: low-medium.** Single fast query per page request; the
cost is dominated by the Comicbox open (#1).

### #3 — `_update_bookmark` queues a task per page hit

`codex/views/reader/page.py:31-46`:

```python
def _update_bookmark(self) -> None:
    do_bookmark = bool(
        self.request.GET.get("bookmark")
        and self.request.headers.get("X-moz") not in self.X_MOZ_PRE_HEADERS
    )
    if not do_bookmark:
        return

    auth_filter = self.get_bookmark_auth_filter()
    comic_pks = (self.kwargs.get("pk"),)
    page = self.kwargs.get("page")
    updates = {"page": page}

    task = BookmarkUpdateTask(auth_filter, comic_pks, updates)
    LIBRARIAN_QUEUE.put(task)
```

Already async — request thread doesn't pay the bookmark write cost.
Good shape.

The frontend can suppress bookmarking via `?bookmark=0` (and Firefox
prefetch hints are filtered). Reasonable.

The librarian thread that processes `BookmarkUpdateTask` is shared;
high-throughput page reads queue many tasks. Whether the librarian
queue throttles or the librarian processes them serially is a
separate concern. Browser-views perf project's #18 (bookmark write
batching) was the analogous concern there.

Mitigations:

- **Coalesce page-bookmark updates.** A user reading at one page per
  3 seconds enqueues ~20 tasks/minute. Each task does a single UPDATE.
  Coalescing in the librarian queue (only the latest page-update
  per `(user, comic)` matters) would reduce DB write volume to ~1/min.
  - Out of scope for view perf; belongs to a librarian-perf project.

**Severity: low for the request-thread.** Out of scope for this
plan but worth flagging for librarian-perf.

### #4 — PDF format negotiation per request

`codex/views/reader/page.py:58-62`:

```python
pdf_format = (
    PageFormat.PIXMAP.value
    if self.request.GET.get("pixmap", "").lower() not in FALSY
    else ""
)
```

Cheap: dict lookup + string compare. Fine.

`codex/views/reader/page.py:68-75`:

```python
if (
    comic.file_type == FileTypeChoices.PDF.value
    and pdf_format not in _PDF_FORMAT_NON_PDF_TYPES
):
    content_type = _PDF_MIME_TYPE
else:
    content_type = self.content_type
```

Cheap. Fine.

**Severity: none.**

### #5 — No server-side caching on the page endpoint

`codex/urls/api/reader.py:20-24`:

```python
path(
    "<int:pk>/<int:page>/page.jpg",
    cache_control(max_age=PAGE_MAX_AGE, public=True)(ReaderPageView.as_view()),
    name="page",
),
```

Only `cache_control` is applied — sets HTTP cache headers so the
client's browser caches the page bytes for `PAGE_MAX_AGE` (one
week). The server doesn't cache the response body itself.

For repeat page hits (e.g. user re-reads a comic; multiple
sessions across a household) the server re-extracts every page
even though the bytes are immutable.

Mitigations:

- **`cache_page(PAGE_MAX_AGE)` wrap.** Like the cover endpoint
  (`codex/urls/opds/binary.py:34-38`), wrap with `cache_page` +
  `vary_on_cookie` (or `vary_on_headers("Cookie", "Authorization")`
  if Basic / Bearer auth applies). The page bytes are user-scoped
  via ACL but identical across users with access to the same
  library — the Vary header keys per user/auth scheme. Same
  trade-off as OPDS Stage 2.
  - **Concern:** page byte payloads are large (~100–500 KB per
    page). A cache holding many pages × many comics × many users
    fills disk fast. The default cache backend is filesystem-based
    (see `codex/settings/__init__.py:512`) with `MAX_ENTRIES =
    10000`. With 200-page comics × 100 users × shared-library
    scenarios, the cache spills its bound quickly and evicts.
    Bounded-cache effectiveness worth measuring before
    scheduling.
- **Hybrid client + server cache.** `cache_control(public=True)`
  already lets clients cache. A reverse proxy (nginx, Caddy) in
  front of Granian can also cache by URL — moves the cache layer
  out of the Django process. Worth documenting as the
  recommended deployment shape.

**Severity: high if archive-open cost (#1) is high; low otherwise.**
Caching response bytes only helps when the underlying extraction
is expensive. With #1 fixed (or with archives that are cheap to
re-open), this matters less.

### #6 — Distinct on the comic queryset

`codex/views/reader/page.py:52`:

```python
qs = Comic.objects.filter(acl_filter).only("path", "file_type").distinct()
```

The `.distinct()` is required because the ACL filter joins through
`codex_library_groups` which can produce duplicate rows. Removing
it would risk leaking comics that match multiple group memberships.
Not a real perf concern at single-comic-pk granularity (the LIMIT 1
implied by `.get(pk=...)` collapses duplicates anyway).

The browser-views perf project verified `distinct` necessity for
the multi-row queryset path; for single-row this is mechanical.
Could drop, but the gain is invisible.

**Severity: trivial.** Leave as-is.

## Out of plan

- **Comicbox internals** — page extraction performance, archive-open
  cost variance across CBZ / CBR / PDF. Tuning belongs to the
  comicbox project, not codex.
- **Frontend prefetch behavior.** Whether the reader pre-fetches N+1
  / N+2 / N+3 pages affects perceived latency and shapes #1's
  caching strategy. Out of scope for view-side analysis.
- **Librarian bookmark-task throttling** — see #3.

## Open questions

- **What's the actual archive-open cost distribution?** CBZ
  (zip): typically <5 ms cold open. CBR (rar): 10–30 ms. PDF:
  10–100 ms depending on pages and renderer. Production traffic
  data on file_type distribution + per-type wall time would
  prioritize #1 vs. #5.
- **What fraction of page hits are repeat reads?** Determines
  whether server-side caching (#5) is worth the disk pressure.
- **Reader UI prefetch pattern?** If the frontend prefetches +1,
  +2, +3 ahead, the archive-open cache (#1) windows naturally
  to the next 3 pages. If it prefetches +20 (full chapter), the
  cache strategy changes shape.
- **Worker pool sizing.** Multi-worker Granian deployments
  multiply per-worker caches. The archive-open cache (#1) needs to
  be shared across workers (e.g. via a sidecar process) or the
  win evaporates with worker count.
