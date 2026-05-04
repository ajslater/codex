# Cover daemon perf — plan

`codex/librarian/covers/` is small (6 files, ~440 LOC) — single
plan file, no meta split.

## Why this matters

The cover thread sits behind every newly-imported comic: the
importer enqueues `CoverCreateTask(pks=…)` with the freshly created
pk batch, and the cover thread serializes through them one at a
time. Each item runs an image-decode + LANCZOS resize + WEBP
encode pipeline that's heavily CPU-bound. On a laptop with 8
cores doing nothing, only one core is in play.

The frontend's bookmark / library tabs also rely on these
thumbnails — a fresh import of 10,000 comics holds the cover queue
for a long time, during which the cards in the browser show the
per-type SVG fallback (cover-cleanup PR #605) instead of real
art.

Single-cover requests via the cover endpoint
(`/api/v3/c/<pk>/cover.webp` 202 polling path, PR #606) also pass
through this thread. Front-of-the-line throughput matters.

## Scope

```
codex/librarian/covers/
├── __init__.py
├── coverd.py       CoverThread (queue dispatcher) — 36 LOC
├── create.py       CoverCreateThread — image pipeline, 165 LOC
├── path.py         CoverPathMixin — hex-path helpers, 41 LOC
├── purge.py        CoverPurgeThread — cleanup, 114 LOC
├── status.py       CoversStatus dataclasses — 42 LOC
└── tasks.py        CoverTask shapes — 49 LOC
```

Plus the live producers (read-only context for the plan):

- `codex/librarian/scribe/importer/create/comics.py:173` — fires
  `CoverCreateTask(pks=created_pks, custom=False)` after each
  importer batch.
- `codex/librarian/scribe/importer/delete/covers.py:14` —
  `CoverRemoveTask` on delete.
- `codex/views/admin/tasks.py:76` —
  `CoverRemoveAllTask` / `CoverCreateAllTask` / `CoverRemoveOrphansTask`
  from admin.
- `codex/views/browser/cover.py:104` — `CoverCreateTask(pks=(pk,))`
  on the 202 polling path.

## Hot path

`_bulk_create_comic_covers` (`codex/librarian/covers/create.py:138-158`):

```python
for pk in pks:
    self._bulk_create_comic_cover(pk, status, custom=custom)
```

Per iteration (`_bulk_create_comic_cover` →
`create_cover_from_path`):

1. `model.objects.only("path").get(pk=pk).path` — one SELECT
2. Read comic file, extract cover via comicbox (CPU + I/O)
3. PIL `Image.open` + `thumbnail(LANCZOS, reducing_gap=3.0)` +
   `save("WEBP", method=6)` (heavy CPU)
4. `os.replace`-based atomic write to disk (I/O)
5. Status update broadcast

Steps 2–3 dominate. They're embarrassingly parallel — each comic
is independent. Today they run serially on one thread of one
process; multiprocessing is the obvious lever.

## Findings

### F1 — Pre-fetch DB paths in the parent **(pure refactor)**

`codex/librarian/covers/create.py:78-79`:

```python
model = CustomCover if custom else Comic
db_path = model.objects.only("path").get(pk=pk).path
```

Today each cover-creation iteration hits the DB serially —
`N` SELECTs for `N` covers. Move to a single batched
`model.objects.filter(pk__in=pks).values_list("pk", "path")` in
the parent before submitting work, then thread the resolved
`db_path` into the worker as a pre-fetched argument.

**Why first**: F3 (multiprocessing) needs to pass `db_path` into
worker subprocesses. With per-iteration DB reads, the worker
would need its own Django connection; pre-fetching collapses N
SELECTs to 1 AND removes Django from the worker entirely.

**Fix sketch**:

```python
def _resolve_db_paths(self, pks, *, custom):
    model = CustomCover if custom else Comic
    return dict(
        model.objects.filter(pk__in=pks).values_list("pk", "path")
    )
```

### F2 — Skip-existing pre-filter in the parent **(small win)**

`codex/librarian/covers/create.py:121-123`:

```python
cover_path = self.get_cover_path(pk, custom=custom)
if cover_path.exists():
    status.decrement_total()
else:
    ...  # actual work
```

The `exists()` stat today happens inside the per-iteration body.
Lift it to the parent so the iteration list (and the eventual
worker submissions in F3) only contains pks that actually need
work. Drops dispatch overhead for already-cached covers — matters
on `CoverCreateAllTask` re-runs.

```python
def _filter_pending_pks(self, pks, *, custom):
    pending = []
    for pk in pks:
        if not self.get_cover_path(pk, custom=custom).is_file():
            pending.append(pk)
    return pending
```

### F3 — `ProcessPoolExecutor` for the cover pipeline **(headline)**

`codex/librarian/covers/create.py:138-158`. The serial loop
becomes a worker-pool dispatch. Image decode + resize + encode
runs in subprocesses; the parent thread writes results to disk
and updates status as workers complete.

**Why processes, not threads**: image processing in PIL hits
C extensions that release the GIL inconsistently; a thread pool
shows mixed gains depending on the encoder path. Process pool
sidesteps the GIL entirely. Each subprocess loads PIL +
comicbox once and serves multiple covers over its lifetime.

**Worker shape** — top-level function, picklable:

```python
def _worker_create_cover(args) -> tuple[int, bytes, str | None]:
    """Render one cover. Picklable; no Django access."""
    pk, db_path, cover_path_str, custom = args
    try:
        if custom:
            with Path(db_path).open("rb") as f:
                image_data = f.read()
        else:
            with Comicbox(db_path, config=COMICBOX_CONFIG) as car:
                image_data = car.get_cover_page(pdf_format="pixmap")
        if not image_data:
            return pk, b"", "empty cover"
        with BytesIO(image_data) as image_io, Image.open(image_io) as img:
            img.thumbnail(_THUMBNAIL_SIZE, Image.Resampling.LANCZOS,
                          reducing_gap=3.0)
            buf = BytesIO()
            img.save(buf, "WEBP", method=6)
        return pk, buf.getvalue(), None
    except Exception as exc:  # noqa: BLE001
        return pk, b"", repr(exc)
```

**Parent dispatch** — `as_completed` for streaming results:

```python
def _bulk_create_comic_covers(self, pks, *, custom):
    pks = self._filter_pending_pks(pks, custom=custom)
    if not pks:
        return 0
    db_paths = self._resolve_db_paths(pks, custom=custom)

    work_items = [
        (pk, db_paths[pk], str(self.get_cover_path(pk, custom=custom)), custom)
        for pk in pks
        if pk in db_paths
    ]
    status = CreateCoversStatus(0, len(work_items))
    self.status_controller.start(status)
    try:
        executor = self._get_or_create_pool()
        for future in as_completed(executor.submit(_worker_create_cover, w)
                                   for w in work_items):
            pk, thumb_bytes, err = future.result()
            cover_path_str = str(self.get_cover_path(pk, custom=custom))
            self.save_cover_to_cache(cover_path_str, thumb_bytes)
            if err:
                self.log.warning(f"Cover for pk={pk} failed: {err}")
            status.increment_complete()
            self.status_controller.update(status)
    finally:
        self.status_controller.finish(status)
    return status.complete or 0
```

**Disk write stays in the parent**: workers return bytes, the
parent calls `save_cover_to_cache` (which already does the
atomic-replace dance). This serializes file writes, avoids race
conditions on duplicate work, and keeps the existing zero-byte
"tried and failed" sentinel intact (`save_cover_to_cache(path,
b"")` writes the marker).

### F4 — Lazy + persistent pool lifecycle **(bundles with F3)**

Cold-starting `ProcessPoolExecutor(max_workers=N)` forks N
subprocesses; each loads Django settings, PIL, comicbox. ~1–2
seconds wall time on first use.

For the per-request 202-poll path
(`CoverCreateTask(pks=(pk,), custom=...)`), a one-shot pool
allocation per call would make single covers slower than the
current serial path. Lazy-create on first use; keep alive for
the thread's lifetime.

```python
class CoverCreateThread(...):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pool: ProcessPoolExecutor | None = None

    def _get_or_create_pool(self) -> ProcessPoolExecutor:
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=COVER_WORKERS)
        return self._pool

    @override
    def stop(self) -> None:
        if self._pool is not None:
            # Don't wait for outstanding tasks; the thread is
            # shutting down. Outstanding cover work is queued in
            # workers and will be GC'd with the subprocesses.
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None
        super().stop()
```

### F5 — `CODEX_COVER_WORKERS` setting **(bundles with F3)**

Default to `min(os.cpu_count() or 1, 8)`. Cap at 8 to bound
peak RAM (each worker loads PIL + comicbox plus an open image —
~50–100 MB peak). Honor the env var for advanced operators.

```python
# codex/settings/__init__.py
COVER_WORKERS = int(os.environ.get(
    "CODEX_COVER_WORKERS",
    min(os.cpu_count() or 1, 8),
))
```

Document in the deploy docs / env-var section alongside other
`CODEX_*` knobs.

### F6 — Single-pk inline fast path **(speculative — defer)**

For `CoverCreateTask(pks=(pk,))` (the 202-poll request path),
dispatching one task to the pool adds queue + IPC overhead — a
few ms — vs. running inline. With the pool already warm, the
overhead is negligible relative to the actual cover work
(typically 10s–100s of ms). **Defer** unless benchmarks show
single-pk latency regressing.

### F7 — `purge_cover_paths` parallelization **(skip)**

`unlink()` is a single syscall; serial is fast enough. Pool
overhead would dominate. Skip.

### F8 — Stale `create_cover_from_path` docstring **(cleanup)**

`codex/librarian/covers/create.py:74` says
"Called from views/cover" — verified false: only
`_bulk_create_comic_cover` calls it. The view-side cover
endpoint enqueues `CoverCreateTask` and returns 202; it doesn't
invoke `create_cover_from_path` directly. Drop the misleading
comment as part of the F3 refactor.

### F9 — Empty `@dataclass` decorators **(cleanup)**

`codex/librarian/covers/tasks.py:9-21` — `CoverTask`,
`CoverRemoveAllTask`, `CoverRemoveOrphansTask`,
`CoverCreateAllTask` all carry `@dataclass` decorators with no
fields. The decorator generates `__init__`/`__repr__`/`__eq__`
shells — harmless but noise. Either drop the decorators or
declare an explicit `_marker: bool = field(default=True,
init=False)` for typed clarity. Cosmetic; bundle if convenient.

### F10 — Status update batching **(speculative — defer)**

`status_controller.update(status)` broadcasts via WebSockets per
cover completion. With a pool churning out covers at 8× the
single-thread rate, the notifier queue depth grows. Could batch
updates into chunks of K completions to reduce broadcast
frequency. Defer until benchmarks show notifier saturation.

### F11 — Memory ceiling guidance **(documentation)**

Per-worker peak: PIL + comicbox + the largest cover image (rare
but possible: a 4000×6000 cover bitmap). At 8 workers ≈ 800 MB
worst case. Document in the deploy docs so operators on memory-
tight installs (e.g. NAS with 1 GB RAM) know to override
`CODEX_COVER_WORKERS=2` or similar.

## Suggested ordering

1. **F1** — pre-fetch DB paths. Pure refactor, no thread changes.
   Land first; F3 builds on it.
2. **F2** — skip-existing pre-filter. Bundle with F1; same
   refactor unit.
3. **F8 + F9** — cleanups. Bundle anywhere.
4. **F3 + F4 + F5** — the big change. Process pool, lazy
   creation, settings knob. Single PR; the unit of risk is the
   subprocess introduction.

## Methodology

For F3:

1. **Microbench under `tests/perf/cover_microbench.py`**:
   ```python
   from time import perf_counter
   from codex.librarian.covers.create import CoverCreateThread
   # snapshot N pks from a populated DB
   pks = list(Comic.objects.values_list("pk", flat=True)[:50])
   start = perf_counter()
   CoverCreateThread._bulk_create_comic_covers(thread_self, pks, custom=False)
   wall = perf_counter() - start
   print(f"{len(pks)} covers in {wall:.2f}s ({len(pks)/wall:.1f} cov/s)")
   ```
   Run before and after F3. Expect roughly Nx speedup where N =
   `CODEX_COVER_WORKERS` (saturated by I/O above ~4 workers).

2. **Memory profile** under `tracemalloc` or RSS sampling — pin
   the per-worker steady-state ceiling, validate the 100 MB
   estimate.

3. **Subprocess safety smoke test**: trigger
   `CoverCreateAllTask` on a populated dev DB, watch the
   librarian status broadcasts. Confirm:
   - All covers complete (no zombie subprocesses).
   - No DB-connection-related crashes (workers don't touch ORM).
   - Pool shuts down cleanly on thread stop.

## Verification

- `make test-python` clean across all fixes.
- Single-cover request (`/api/v3/c/<pk>/cover.webp` 202 path):
  cover materializes within the FLOOD_DELAY-equivalent window.
  No regression vs current.
- Bulk request (`CoverCreateTask(pks=N)` for N=100): wall-clock
  time drops by ~`CODEX_COVER_WORKERS` factor.
- `CoverCreateAllTask` on a populated DB: completes without
  zombie subprocesses or DB connection errors.

## Risks

- **comicbox subprocess safety untested.** The library opens
  external archive files (CBR / CBZ / PDF) and reads bytes.
  Worker calls construct a fresh `Comicbox` context per
  invocation — no shared state. Should be safe; verify via the
  smoke test above.
- **PIL subprocess safety.** PIL is process-safe per its docs:
  module-level state is read-only after import. Each worker
  imports PIL once at startup; the per-call `Image.open` /
  `save` cycle is self-contained.
- **`COMICBOX_CONFIG` import-time cost.** The worker imports
  `codex.settings` to read `COMICBOX_CONFIG` — pulls in Django
  settings, which is heavy. Lazy-evaluate inside the worker
  function, or pass the config dict as a worker arg pickled
  from the parent. Latter avoids re-importing Django in each
  subprocess.
- **Loguru in subprocesses.** `loguru` has a global
  `logger` per process. Workers configure their own; output
  goes to whatever the parent's stderr/log file is via
  inheritance. Verify log lines from worker exceptions still
  appear in the librarian log. Fallback: workers return error
  strings, parent logs. The F3 sketch already does this.
- **Pool shutdown on hard kill.** If the cover thread is
  killed without invoking `stop()`, the worker subprocesses
  become orphans. `ProcessPoolExecutor` registers an `atexit`
  handler that cleans up; should be fine. If not, add a
  `signal` handler.
- **Memory under heavy worker count.** Documented in F11.
  Default cap of 8 keeps peak ~800 MB.

## Out of scope

- **Cover quality / format changes.** WEBP method=6 + LANCZOS
  reducing_gap=3.0 are existing tunables; perf-orthogonal.
- **Per-comic cover annotations on browser cards.** Already
  done in the cover-cleanup project (PRs #605, #606).
- **Replacing comicbox / PIL.** Out of scope; substantial
  rewrite.

## References

- `codex/librarian/covers/` — the surface
- `codex/librarian/scribe/importer/create/comics.py:173` — main
  producer of `CoverCreateTask`
- `codex/views/browser/cover.py:104` — the 202-poll path
  producer (single pk per task)
- Python `concurrent.futures.ProcessPoolExecutor` docs — pool
  lifecycle + `as_completed`
