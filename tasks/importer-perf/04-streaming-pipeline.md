# 04 — Streaming pipeline architecture

The biggest refactor in this plan — and the one to ship **last**,
after sub-plans 01–03 + 05–06 prove out the surgical wins. This
sub-plan addresses memory rather than CPU, which only matters at
the 600k ceiling and on memory-constrained hosts (Raspberry Pi,
small VPS).

## The problem: peak memory grows linearly with library size

The current pipeline is **all-at-once**: every phase reads the
full `self.metadata` dict populated by prior phases and writes
new keys for the next phase. Memory is held until the very last
phase (`full_text_search`) clears it.

Tracked keys (`grep "self.metadata\[" codex/librarian/scribe/importer/`):

| Key | Holds | Approx size for 600k import |
| --- | --- | --- |
| `EXTRACTED` | path → comicbox_md_dict | ~3 GB (filtered) |
| `CREATE_COMICS` | list[Comic instance] | ~1.5 GB |
| `UPDATE_COMICS` | list[Comic instance] | ~1.5 GB on repeat imports |
| `LINK_FKS` | path → {field → key_tuple} | ~500 MB |
| `LINK_M2MS` | path → {field → set[key_tuple]} | ~1 GB |
| `CREATE_FKS` / `UPDATE_FKS` | model → set[key_tuple] | ~200 MB |
| `QUERY_MODELS` | model → set[key_tuple] | ~200 MB |
| `FTS_CREATE` / `FTS_UPDATE` | path → fts payload | ~500 MB |
| `CREATE_COVERS` / `UPDATE_COVERS` | cover task payload | ~200 MB |
| `FIS` / `CREATE_FIS` / `UPDATE_FIS` | failed-import rows | ~50 MB |

**Peak working set: ~8-10 GB** for a fresh 600k-comic import. On
a Raspberry Pi 4 (4 GB RAM) this OOM-kills the process. On a
Raspberry Pi 5 (8 GB) it swaps. On real servers it's fine but
wasteful.

## The opportunity: the pipeline is naturally chunkable

Comics don't reference each other. A batch of comics can flow
through the full extract → query → create → link cycle
independently of the rest of the library. **Reference data**
(Publisher, Imprint, Series, Volume, named tag rows) does need
global awareness: "Marvel" must not be inserted twice.

That gives the natural split:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PHASE-1: REFERENCE DATA (all-at-once, small in size)     │
│    extract(all paths) → aggregate FK/M2M names              │
│    query missing reference data                             │
│    create FK rows (Publisher, Imprint, ..., named tags)     │
│    →  output: pk maps for every reference model             │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. PHASE-2: COMIC INGESTION (streaming, chunk size N)       │
│    for chunk in chunks(paths, N):                           │
│        extract(chunk) → comic field values + link keys      │
│        prune existing links                                 │
│        create / update comics                               │
│        link M2Ms                                            │
│        emit fts payload                                     │
│        clear chunk-local state                              │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. PHASE-3: FINALIZE                                        │
│    fail_imports                                             │
│    delete                                                   │
│    full_text_search (sync watermark)                        │
└─────────────────────────────────────────────────────────────┘
```

Memory in phase 2 is bounded by the chunk size, not the library
size. Reference data in phase 1 is O(unique entries), which is
small even at the 600k ceiling.

## Phase-1 sizing

For a fresh 600k-comic library:

| Reference model | Approx unique rows | Memory |
| --- | --- | --- |
| Publisher | ~500 | < 1 MB |
| Imprint | ~5k | < 5 MB |
| Series | ~30k | ~30 MB |
| Volume | ~150k | ~150 MB |
| Folder | ~50k | ~50 MB |
| Character / Genre / Location / Story / Team / Tag | ~10-100k each | ~100 MB total |
| Credit / Identifier / StoryArcNumber | ~500k–1M | ~500 MB |

**Total phase-1 footprint: ~800 MB** — fits comfortably even on a
2 GB Pi.

The phase-1 extract pass needs only the **link-key fields** from
each comic (`publisher`, `imprint`, `series`, `volume`,
`credits[].person`, `credits[].role`, `tags`, `genres`, etc.) —
not the full metadata. Two ways to get there:

A. Use `comicbox.to_dict(keys=...)` from sub-plan 06 to extract
   only the link-key fields in phase 1, then re-extract full
   metadata in phase 2 chunks.

B. Extract everything in phase 1 but stream the metadata to a
   spill file (per-comic JSONL) keyed by path. Phase 2 chunks
   read from disk.

Option A doubles archive opens (twice per comic). Option B writes
~3 GB to disk once, reads it back streaming. **Option B is
better** for any library where archives live on slower storage
than the codex cache directory; archives are typically on a media
disk while the cache (`ROOT_CACHE_PATH`,
`settings/__init__.py:523` = `CONFIG_PATH / "cache"`) lives
alongside the codex DB on faster storage.

Spill location: **`ROOT_CACHE_PATH / "import_cache.jsonl"`**.
Reasons:

- Persistent across reboots (unlike `/tmp` on tmpfs systems where
  a 5 GB spill would OOM the tmpfs ramdisk).
- Same volume as the codex DB, so atomicity / cleanup is
  consistent with other codex state.
- Already a directory codex creates and manages
  (`DEFAULT_CACHE_PATH.mkdir(...)`), so no new mount-point
  decisions for the user.
- Survives a daemon restart, which the resume-from-watermark
  scheme below depends on.

A third option:

C. Single-pass extract that **publishes** to two places: link-key
   summaries to phase-1's in-memory aggregator, and full metadata
   to a chunk queue consumed by phase-2 in parallel.

Option C is the streaming-pipeline ideal but requires phases 1
and 2 to overlap, which is incompatible with the current
"phase 1 must finish before phase 2 starts" requirement (the FK
creates need to be done before any comic can be created with
those FKs).

**Recommendation: option B**. Single-pass extract → JSONL spill
file → phase 1 aggregates from spill → phase 2 streams chunks
from spill. Disk I/O is fast (sequential, OS-page-cached) and
memory is bounded.

## Phase-2 chunking

### Chunk size: dynamic, sized to available memory

Hardcoding `CHUNK_SIZE = 5000` is wrong. A 32 GB server can
afford 50k-comic chunks; a 1 GB Pi can't even hold 5k. Codex
already has the right tool — `codex/librarian/memory.py`'s
`get_mem_limit()` reads cgroups2/cgroups1 limits (Docker, Pi
under systemd) before falling back to `psutil.virtual_memory()`.
Use it:

```python
# codex/librarian/scribe/importer/init.py (sketch)
from codex.librarian.memory import get_mem_limit

# Empirically, each comic in flight through phase 2 carries
# ~6-12 KB of working set (Comic instance + LINK_FKS dict +
# LINK_M2MS sets + FTS payload). Round up to 16 KB for safety.
_PER_COMIC_BYTES = 16 * 1024
# Hold phase 2 to at most a quarter of the process memory budget,
# leaving room for phase-1 pk_maps (~800 MB worst case) +
# SQLite cache (~512 MB) + overhead.
_PHASE_2_MEM_FRACTION = 0.25
_CHUNK_FLOOR = 1000
_CHUNK_CEILING = 50000

def _compute_chunk_size(self) -> int:
    """Size phase-2 chunks to fit available memory."""
    mem_budget = get_mem_limit("b") * _PHASE_2_MEM_FRACTION
    raw = int(mem_budget // _PER_COMIC_BYTES)
    return max(_CHUNK_FLOOR, min(_CHUNK_CEILING, raw))
```

Indicative numbers:

| Host | mem_limit | chunk_size |
| --- | --- | --- |
| Pi 4 (4 GB) | 4 GB → 1 GB phase-2 budget | ~50k → capped to 50k |
| Pi 4 cgroup-limited (2 GB) | 2 GB → 512 MB | ~32k |
| Pi 3 (1 GB) | 1 GB → 256 MB | ~16k |
| Pi 0 W 2 (512 MB cgroup) | 512 MB → 128 MB | ~8k |
| Tiny container (256 MB) | 256 MB → 64 MB | ~4k |
| Smallest viable (64 MB cgroup) | 64 MB → 16 MB | floor ~1000 |

The floor of 1000 protects against pathological tiny chunks where
the per-batch SQL overhead would dominate. The ceiling of 50k
protects against integer overflow / unbounded peak memory on
absurdly large hosts.

Expose the multiplier as a config knob for advanced users:

```python
IMPORTER_PHASE_2_MEM_FRACTION = get_float(
    CODEX_CONFIG, "importer.phase_2_mem_fraction", default=0.25
)
```

```python
for chunk_paths in batched(all_paths, self._compute_chunk_size()):
    chunk_md = read_chunk_from_spill(chunk_paths)

    chunk_link_fks, chunk_link_m2ms = aggregate_chunk_links(chunk_md)

    # Prune existing links — same code as today, but per-chunk:
    self.metadata[LINK_FKS] = chunk_link_fks
    self.metadata[LINK_M2MS] = chunk_link_m2ms
    self.query_prune_comic_fk_links(status)
    self.query_prune_comic_m2m_links(status)

    # Create comics — same code, per-chunk:
    self.metadata[CREATE_COMICS] = build_create_list(chunk_md)
    self.metadata[UPDATE_COMICS] = build_update_list(chunk_md)
    self.create_and_update_comics(status)

    # Link M2Ms — same code, per-chunk:
    self.link_prepare(status)
    self.link_many_to_many(status)

    # Emit fts payload to a chunk-fts list (consumed in phase 3):
    self.fts_emit_chunk(status)

    # Clear all chunk-local state.
    for key in (LINK_FKS, LINK_M2MS, CREATE_COMICS, UPDATE_COMICS,
                CREATE_FKS, UPDATE_FKS, FTS_CREATE, FTS_UPDATE):
        self.metadata.pop(key, None)
```

**Per-chunk memory** (illustrative; the dynamic sizer above
chooses the actual chunk):

| State | 5k chunk | 10k chunk | 32k chunk |
| --- | --- | --- | --- |
| Comic instances | ~12 MB | ~25 MB | ~80 MB |
| LINK_FKS | ~4 MB | ~8 MB | ~25 MB |
| LINK_M2MS | ~8 MB | ~16 MB | ~50 MB |
| FTS payloads | ~4 MB | ~8 MB | ~25 MB |
| Working overhead (Python objects, Django ORM cache) | ~2 MB | ~3 MB | ~10 MB |
| **Total** | **~30 MB** | **~60 MB** | **~190 MB** |

Plus phase-1 pk_maps held throughout phase 2 — sized by library
content, typically ~200 MB to ~800 MB. The dynamic chunk sizer
above is calibrated against this overhead so total peak stays
within `mem_limit × _PHASE_2_MEM_FRACTION + ~1 GB` headroom.

## Failure recovery: the underrated win

A 600k-comic import that takes 30+ minutes will get interrupted
sometimes — power blip, OOM, user ctrl-c, daemon restart. The
current pipeline either:

- Finishes (success), or
- Aborts mid-phase, leaving the metadata dict and any committed
  rows in a half-state that the next run starts over from
  scratch.

A streaming pipeline gives **per-chunk checkpointing**:

```python
# After each chunk finishes successfully, persist the watermark.
LibraryImportProgress.objects.update_or_create(
    library=self.library,
    defaults={"completed_chunk_index": chunk_idx},
)
```

On resume, skip chunks ≤ watermark. Each chunk's writes are
already wrapped in `transaction.atomic` (sub-plan 05) so the
chunk is all-or-nothing. The watermark is the natural restart
point.

Worth a one-line note: this isn't free. It requires:

1. A new `LibraryImportProgress` model (or repurpose the existing
   `Library.last_poll`).
2. The chunk index → path map to be deterministic across runs
   (sort `all_paths` lexically before chunking).
3. A "resume" code path that skips reference-data creation for
   parents already created in a prior partial run.

Item 3 is the gotcha — phase 1 must be idempotent against
already-created reference rows. The existing
`bulk_create(update_conflicts=True)` flow handles this, but it
still **runs** the full create path. Could be optimized to skip
phase 1 entirely on resume by reading the existing reference rows
into pk_maps directly. Out of scope for the initial cut.

## Risks

### Risk: cross-chunk reference data mutation

If chunk 47 introduces a new Publisher "Indie Press LLC", that
Publisher must be queryable by chunk 48. Two cases:

- **Phase-1-only reference creation**: phase 1 sees every comic's
  link keys (via the spill-file aggregate), so every Publisher,
  Imprint, etc. is created before phase 2 starts. Chunk 48 finds
  "Indie Press LLC" in the pk_map. ✓
- **Late-discovered references**: chunk 47 has a credit role
  "Cover Pencils" that wasn't aggregated in phase 1 (because
  phase 1's extract was lossy and missed it). Chunk 48's
  CreditRole pk_map is missing it.

**Mitigation**: phase-1 aggregate must be exhaustive. Use the
same field-projection set in phase 1's extract as in phase 2's.
Don't trade off completeness for phase-1 speed.

### Risk: spill-file disk usage

For 600k comics, the JSONL spill file is ~3-5 GB. The
`ROOT_CACHE_PATH` location (decided above, on the config volume
alongside the codex DB) is the right place — but on small-disk
hosts it can still bite. Worst case is a Pi with a 32 GB SD card
that's already 80% full with comic covers, FTS index, and DB
backups; a 5 GB spill on top fills the disk.

**Mitigation**: compress the spill file with zstd (or gzip if
zstd isn't already a dependency — verify; comicbox uses zstandard
indirectly through some PDF backends). Compressed JSONL is
4-10× smaller than raw — a 5 GB spill drops to 500 MB-1 GB.
Decompression is cheap and chunk-streamable, and zstd's
seekable-format extension allows random-access into the spill
file (handy for the resume-from-watermark scheme below).

Also: clean up the spill file in the `finish()` phase, even on
abort. Don't leave 5 GB lying around between imports.

### Risk: `_get_create_update_args` with split phases

This function (sub-plan 02) builds Comic kwargs from a flat
values_tuple by dereferencing FK pks. Per-chunk, the pk_maps
must include every FK referenced by **this chunk**. Since pk_maps
are global (built in phase 1), this is automatic — no special
handling needed. But verify: the current code expects pk_maps for
every FK to be populated; chunked phase 2 must inherit the full
phase-1 pk_maps.

### Risk: status reporting

The current `LibrarianStatus` model expects
`(complete, total)` updates. With chunking, "total" is known
ahead of time (total comics) but "complete" advances per chunk.
The progress bar UI handles this fine. The librarian's per-phase
status messages (`"Aggregating", "Creating Many-to-One", ...`)
need to be re-thought — every phase fires per-chunk, generating a
flicker of identical messages.

**Mitigation**: rate-limit per-chunk status messages. The
existing `_UPDATE_DELTA = 5s` rate-limit in `status_controller`
already handles this for individual updates; the message-text
side just needs `start()` calls deduplicated.

### Risk: test surface

The current importer is integration-tested per phase. Chunked
flow blends phases. Tests need to:

1. Cover the chunk boundary (a comic at chunk N's end and chunk
   N+1's start, where the boundary splits a series).
2. Cover the resume path (kill mid-chunk, restart, verify
   exactly-once semantics).
3. Cover the skip-known-reference path on resume.

Plan to add a parameterized `chunk_size=1` mode for tests, which
exercises the chunk machinery on every comic.

## Suggested commit shape

This is a multi-PR project, not a single PR. Suggested sequence:

1. **PR-A: spill file infrastructure** — add the JSONL spill
   writer + reader + chunk iterator. No behavior change. Spill is
   produced but the importer still operates all-at-once. Adds
   ~300 LOC.

2. **PR-B: phase-1 / phase-2 split** — flip the importer to
   read from spill in two passes. Memory drops but no chunking
   yet. ~500 LOC; large but mostly mechanical.

3. **PR-C: chunked phase 2** — actually chunk the comic
   ingestion. Builds on PR-B. ~300 LOC.

4. **PR-D: resume-from-watermark** — new model + skip logic. ~200
   LOC.

5. **PR-E: spill compression** — wrap the JSONL with zstd.
   ~50 LOC.

Ship A → B → C with multi-week soak in between. D and E are
optional follow-ups.

## Why this ships LAST

Three reasons:

1. **The surgical wins (sub-plans 01-03 + 05-06) are independent
   and compose**. Each shaves a real chunk of wall-clock without
   touching pipeline shape. They build a body of evidence for
   "the importer can be much faster" before we propose the big
   refactor.

2. **Memory pressure is the secondary motivator** for most users.
   Most codex installs run on > 4 GB hosts where the current
   ~10 GB peak is uncomfortable but not fatal. The CPU wins from
   01-03 ship value to everyone; the streaming-pipeline ships
   value to a smaller (but real) audience of resource-constrained
   users.

3. **Risk profile**. A streaming pipeline rewrites the importer's
   data flow. A bug in chunking that causes a Publisher to be
   missed on chunk N would be hard to spot in testing and
   catastrophic in production. Preceding wins are smaller blast
   radius — if they regress, we can revert quickly.

## Test plan

- **Round-trip equivalence**: run the same fixture import
  through the all-at-once and chunked code paths. Assert every
  Comic, FK, M2M row in the resulting DB is bit-identical.
- **Memory ceiling**: run a 100k-comic import under
  `tracemalloc`; assert peak RSS < 1.5 GB.
- **Chunk boundary**: fixture with 11 comics, chunk size 5.
  Comics 4-7 share a Series. Verify Series row is created in
  phase 1, used by both chunks 0 (comics 0-4) and 1 (comics 5-9).
- **Resume**: SIGTERM the importer mid-chunk-3 of a 5-chunk run.
  Restart. Assert chunks 0-2 are skipped, chunk 3 is re-run from
  scratch (atomic rollback), chunks 3-4 complete normally.
- **Compressed spill**: 1k-comic import with zstd. Assert spill
  file size is < 30% of uncompressed equivalent.
- **Wall clock**: 100k-comic dev fixture. Expect chunked
  pipeline within 10% of all-at-once wall clock (memory drops
  shouldn't cost time). If significantly slower, investigate
  before merging.
