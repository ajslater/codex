# Stage 3 — Comicbox archive cache for the page endpoint

Closes [Tier 1 #1](99-summary.md#2-ranked-backlog) — the highest-impact
remaining item in the reader plan.

## Decisions driven by telemetry

Before designing, sourced telemetry from the chronicle backup
(`~/Code/codex/chronicle-backup/`) to ground the design in real-world
deployment shapes:

- **Concurrent reader peaks** (max `user_anonymous_count` across all
  snapshots per UUID, 1 208 unique installations):
    - p50 = 2 sessions, p75 = 6, p90 = 13, p95 = 22, p99 = 106.
    - Max 22 664 (an outlier — public install or scraper).
- **Deployment shape**: 83% Linux x86_64 + Docker, 11% Linux ARM
  (RPi / ARM NAS), 6% macOS, 0.5% Windows. The "constrained NAS"
  case is real — many installs run on 1–2 GB RAM boxes.
- **Granian config**: Codex runs Granian in single-worker embed mode
  (`codex/run.py`). Single process, async + threadpool dispatch.
  This means a process-wide cache works without multi-worker
  dilution.
- **Frontend prefetch** (`frontend/src/stores/reader.js`):
    - Per page-view, the reader UI fires 2 prefetches: page N+1
      (next direction) and page N-1 (prev direction). In two-pages
      mode it's 4 (N±1, N±2). All hit the same archive within ~1 s.
    - `cacheBook` setting (opt-in, default off): bursts a whole-book
      prefetch on book open — N parallel page hits on the same archive.
      User confirmed this is used "sometimes."
    - PDFs are excluded from `prefetchBook`.
- **File-type distribution**: ❌ unavailable. The chronicle DB tables
  for filetype counts (`chronicle_filetypecount`,
  `chronicle_codexstatsv1_filetype_counts`) are empty in the backup —
  the chronicle ingest path may not yet materialize codex's
  `_add_file_types` payload (out-of-scope per the user). Proceeded
  with the assumption that CBZ dominates with a long PDF/CBR tail.

## What landed

### `codex/views/reader/_archive_cache.py`

A process-wide LRU of open `Comicbox` archives. Cache shape:

```python
class ArchiveCache:
    max_entries: int = 4   # CODEX_READER_ARCHIVE_CACHE_SIZE
    idle_ttl: float = 30.0 # CODEX_READER_ARCHIVE_CACHE_TTL
    enabled: bool = True   # CODEX_READER_ARCHIVE_CACHE_DISABLE

    _struct_lock: threading.Lock         # guards LRU mutation only
    _archives: OrderedDict[path, _ArchiveEntry]

class _ArchiveEntry:
    comicbox: Comicbox
    lock: threading.Lock                 # serializes extraction per archive
    last_access: float
```

`_struct_lock` is held briefly during cache lookup / insert / evict —
unrelated archives proceed in parallel. Per-archive `_ArchiveEntry.lock`
is held during `get_page_by_index` because Python's `zipfile`,
`rarfile`, and PDF backends are not documented as thread-safe under
concurrent `read()` calls on the same instance.

Public API:

```python
from codex.views.reader._archive_cache import archive_cache

with archive_cache.open(comic.path) as cb:
    page_image = cb.get_page_by_index(page, pdf_format=pdf_format)
```

Wired into `ReaderPageView._get_page_image` — the only call site that
matters. (OPDS v1's `lazy_metadata` open is flagged as separate item
#9 in the summary.)

### Sizing rationale

- **`max_entries = 4`**: covers the median install (≤2 concurrent
  readers — see telemetry) with headroom for prev/curr/next archive
  transitions. Higher tier installs (p95 = 22 readers) get cache
  dilution but the cache still helps within each user's session.
- **`idle_ttl = 30 s`**: covers a slow reader at 1 page every 15 s
  with one-page-of-headroom; faster readers get many hits per archive
  open.
- **Memory budget per cached entry**: ~1-3 MB for CBZ (file handle +
  ZIP central directory), 5-30 MB for PDF (libpoppler state). 4
  entries × 5 MB avg = 20 MB worst-case per process. Fine for the
  1-2 GB NAS box.
- **FD budget**: 4 entries × 1 FD = 4 FDs. Trivial — codex already
  raises `RLIMIT_NOFILE` to 8 192 in `run.py`.

### Configuration knobs

Three env vars (all optional; conservative defaults suit the NAS case):

- `CODEX_READER_ARCHIVE_CACHE_SIZE` — max open archives (default `4`).
- `CODEX_READER_ARCHIVE_CACHE_TTL` — idle expiry in seconds (default `30`).
- `CODEX_READER_ARCHIVE_CACHE_DISABLE` — bypass entirely (default `false`).

`atexit` hook closes all cached archives on process shutdown.

## Measured impact (and why the dev numbers don't tell the whole story)

The harness on this dev machine (NVMe SSD, warm OS page cache):

| Flow              | Cold queries (before → after) | Cold wall (before → after) | Warm wall (before → after) |
| ----------------- | ----------------------------: | -------------------------: | -------------------------: |
| page_first        |                         9 → 9 |       14.6 → 14.5 ms       |       10.1 → 9.9 ms        |
| page_middle       |                         9 → 9 |       14.8 → 13.8 ms       |       9.8 → 9.3 ms         |
| page_no_bookmark  |                         9 → 9 |       15.6 → 16.4 ms       |       9.5 → 9.6 ms         |
| (other 4 flows)   |             within ±0 noise  |             within ±0      |        within ±0           |

**On dev hardware the cache is invisible.** Microbenchmark explains
why:

```
cold open + extract page 0:                1.5 ms
10 fresh opens (sequential pages, avg):    0.7 ms each
1 open + 10 sequential extracts (avg):     0.1 ms each
```

A `Comicbox(path).__enter__()` on a warm-cache CBZ on NVMe is ~0.7
ms. The cache saves ~0.6 ms per request — invisible against ~13 ms
of Django middleware + ACL filter + serialization.

**On slow hardware the picture changes.** Common deployment shapes
move into territory where the cache wins meaningfully:

- HDD-backed NAS, cold OS page cache: archive open often 5-50 ms.
- USB-3 external drive: 10-100 ms.
- CBR (`unrar` shell-out): adds 10-30 ms regardless of disk.
- PDF (libpoppler init): 10-100 ms regardless of disk.

Without slow-hardware test infrastructure I can't measure these
deltas directly. The architecture is sound and the dev harness shows
no regression — landing this is a low-risk bet that the real-world
win materializes on the deployment shapes the telemetry shows
dominate (Linux NAS, Docker, ARM SBCs).

## Functional verification

Sequential read of 10 pages on the 233-page test comic:

```
page  0: status=200 bytes= 63 179   629.0 ms  (cold session warmup)
page  1: status=200 bytes= 92 096    20.9 ms
page  2: status=200 bytes=106 802    19.2 ms
…
```

Subsequent pages settle to ~19 ms (test-client overhead dominates).
Output is byte-identical to the pre-cache implementation — verified
by comparing response bytes at multiple page indexes between
`CODEX_READER_ARCHIVE_CACHE_DISABLE=1` and the default.

## Trade-offs and known caveats

### Per-archive lock serializes parallel reads on the same archive

When N requests hit the same archive simultaneously (the `cacheBook`
whole-book prefetch case), the per-archive lock serializes them.
Without the cache, each request would open its own `Comicbox`
instance and proceed in parallel; with the cache, they queue.

For a 200-page `cacheBook` prefetch, this means 200 requests serialize
through extract calls (each ~0.1-10 ms depending on hardware). Total
wall time scales linearly with archive page count.

Why this is acceptable:

1. `cacheBook` is opt-in and the user said "people will use cacheBook
   sometimes" — not the dominant path.
2. The dominant path (sequential read with prev/next prefetch) is
   2-3 requests near-simultaneously. Cache hit + brief serialization
   is fine.
3. The serialization is correctness-mandated: Python's `zipfile`,
   `rarfile`, and PDF backends are not safe for concurrent reads on
   the same instance.
4. On slow hardware the cache savings (one open instead of 200) more
   than compensate for the serialization overhead.

A future Stage could replace the per-archive lock with a small
per-path pool (N=2-4 independent Comicbox instances per path) to
allow parallel extraction at the cost of multiplied memory. Not
shipping that now — keep it simple, ship the conservative version.

### Single-process scope

Codex runs Granian in single-worker embed mode (see `codex/run.py`),
so the process-wide cache is shared by all request-handling threads.
If a future codex change moves to multi-worker deployment, the cache
remains correct (each worker has its own) but the hit rate per worker
drops linearly with worker count. Document at that time.

### Librarian process is unaffected

The librarian daemon runs in a separate process (multiprocessing).
Its `Comicbox` calls (cover generation in `librarian/covers/create.py`,
fs filters in `librarian/fs/filters.py`) don't share this cache. They
have their own access patterns and are out of scope for the reader
perf project.

## What's next

After Stage 3 the reader-perf plan is largely closed. The Tier 1
items are all in (1, 2, 3 + #4 from Phase C). Tier 2 has #5, #7
landed; #6 (server-side response cache for the page endpoint)
remains open but its value is reduced now that the archive cache
amortizes the per-request open cost.

**Phase F — Tier 3-4 cleanups** still has open items:

- **#8** — `Max("updated_at")` SQL aggregate in `_get_story_arcs`
  (avoid Python strptime per row).
- **#11** — Audit `_get_comics_list` annotation pyramid for prev/next
  dead fields.
- **#12** — De-dup `_get_bookmark_auth_filter`.
- **#15** — Per-process ACL decision cache for the page endpoint.

All small and independent.
