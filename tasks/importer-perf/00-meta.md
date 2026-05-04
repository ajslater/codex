# Importer perf — meta plan

`codex/librarian/scribe/importer/` is large (62 files,
~5,000+ LOC across 8 phase-specific subdirectories) and central
to the user's workflow. The user's stated goal: take a 600,000-
comic bulk import to a faster wall-clock time without sacrificing
correctness.

This is a meta-plan. The surface is too big for one plan file
and the user explicitly noted "complicated code and hard for a
human to conceptualize all at once." Each sub-plan covers one
phase of the pipeline or one cross-cutting concern, can be
reviewed in isolation, and ships as one PR.

## Why this matters at 600k scale

What's slow at small scale (10s of comics) is invisible. At 600k
comics, even O(N) Python work becomes minutes; an N+1 query
pattern hidden in a per-comic loop becomes hours.

The user noted they've "already spent a while" optimizing. The
easy wins are likely already taken. The remaining wins live in:

1. **N+1 query patterns inside loops** that fire millions of
   small SELECTs across the import — the most common slow-at-scale
   bug shape. Several confirmed below.
2. **Memory pressure** from building per-path metadata dicts for
   the entire batch in `self.metadata` before the next phase runs.
3. **Sub-process boundary cost** in comicbox's parallel reader —
   pickling rich metadata dicts across the IPC channel scales.
4. **SQLite write throughput tuning** — PRAGMAs that only matter
   for bulk ingest.
5. **Comicbox-side parsing** — codex doesn't use most of what
   comicbox returns; cycles spent parsing unused fields.

## Pipeline architecture

`ComicImporter.apply` runs nine phases in sequence
(`importer.py:5-15`):

```python
_METHODS = (
    "init_apply",            # wait for FS ops, init statuses
    "move_and_modify_dirs",  # rename folder DB rows in place
    "read",                  # extract + aggregate metadata
    "query",                 # find existing FK rows
    "create_and_update",     # bulk create FK rows + comics
    "link",                  # wire up M2M relations
    "fail_imports",          # record failed imports
    "delete",                # remove DB rows for deleted files
    "full_text_search",      # sync FTS index
)
```

Data flows through `self.metadata` — a dict keyed by phase outputs
(`EXTRACTED`, `CREATE_COMICS`, `UPDATE_COMICS`, `LINK_FKS`,
`LINK_M2MS`, `QUERY_MODELS`, `CREATE_FKS`, `UPDATE_FKS`, etc.).
Each phase consumes some keys, produces others, and sometimes
deletes the old ones to free memory.

## Surface map

| Phase | Subdirectory | LOC | What it does |
| ----- | ------------ | --- | ------------ |
| init / orchestration | (top-level) | ~750 | `init.py`, `importer.py`, `finish.py`, `const.py` |
| moved | `moved/` | ~430 | Handle file/folder renames without re-extracting metadata |
| read | `read/` | ~870 | comicbox extraction (parallel via `ProcessPoolExecutor`) → aggregate FK + M2M |
| query | `query/` | ~660 | Find existing FK rows; prune already-correct links |
| create | `create/` | ~610 | Bulk-create FK rows, then bulk-create/update comic rows |
| link | `link/` | ~430 | Wire up M2M through-table rows |
| delete | `delete/` | ~200 | Remove DB rows for deleted files |
| failed | `failed/` | ~280 | Record failed imports |
| status | `statii/` | ~250 | Status dataclasses for the librarian status table |

## Confirmed perf hot spots (with line numbers)

### Headline finding — millions of SELECTs in `link_prepare_m2m_links`

`link/prepare.py:105-135`. For each comic in the batch:

```python
for comic_pk, comic_path in comics:
    md = self.metadata[LINK_M2MS][comic_path]
    self._link_prepare_complex_m2ms(...)  # × 4 SELECTs (folders + 3 complex models)
    for field, names in md.items():
        self._link_prepare_named_m2ms(...)  # × ~10 named M2M fields
```

`_link_prepare_named_m2ms`:

```python
pks = (
    model.objects.filter(name__in=names).values_list("pk", flat=True).distinct()
)
```

One SELECT per (comic, M2M field). With 600k comics × ~14 M2Ms,
that's **~8.4 million SELECTs** in this phase alone — almost
certainly the dominant cost of the link step.

Detailed in [01-link-batching.md](./01-link-batching.md). Fix:
batch by model. Build `dict[(model, name) → pk]` once per
import, look up in Python.

### FK creation does per-row SELECTs

`create/foreign_keys.py:60-75`. `_get_create_update_args`
dereferences nested FK references via `field_model.objects.get(...)`
for every row in the create/update batch.

For 600k comics with ~5k unique imprints, the imprint creation
phase fires 5k publisher SELECTs. Series creation: 10k publisher +
imprint SELECTs. Comic creation runs through similar logic.

`create/foreign_keys.py:189`. `_bulk_update_models` does
`obj = model.objects.get(**key_args)` per update tuple. Same shape.

Detailed in [02-create-fk-batching.md](./02-create-fk-batching.md).
Fix: pre-fetch the parent FK lookup map once per model, reuse
during create.

### Query-prune phases iterate per-comic

`query/links_m2m.py:85-104`. `_query_prune_comic_m2m_links_batch`
prefetches all M2M fields for a batch of comics, then walks them
in Python to determine deltas:

```python
comics = (
    Comic.objects.filter(library=self.library, path__in=paths)
    .prefetch_related(*COMIC_M2M_FIELD_NAMES)
    .only(*COMIC_M2M_FIELD_NAMES)
)
for comic in comics.iterator(...):
    self._query_prune_comic_m2m_links_comic(comic, status)
```

Each comic iteration walks ~14 M2M relations and rebuilds tuple
keys. For 600k comics that's ~8.4M Python iterations + the
Django ORM overhead.

`query/links_fk.py` similar shape for FK pruning.

Detailed in [03-query-prune.md](./03-query-prune.md).

### Moved phase: per-comic Folder.objects.get / filter

`moved/comics.py:61-68`. Per moved comic:

```python
comic.parent_folder = Folder.objects.get(path=new_path.parent)
new_folder_pks = frozenset(
    Folder.objects.filter(path__in=new_path.parents).values_list("pk", flat=True)
)
```

Two SELECTs per moved comic. 600k moves → 1.2M SELECTs.

Bundled into [03-query-prune.md](./03-query-prune.md) since it's
the same kind of "batch by model" fix.

### Memory pressure from all-at-once batch architecture

`init.py` reads metadata for ALL paths into `self.metadata[EXTRACTED]`.
`aggregate_metadata` then transforms ALL into `CREATE_COMICS` /
`LINK_FKS` / `LINK_M2MS`. `query` mutates them. `create_and_update`
consumes them.

For 600k comics, peak memory holds the whole batch's per-path
dicts. At ~1-5 KB per dict, that's 0.6-3 GB of pure Python dict
overhead during the overlap windows between phases.

Detailed in [04-streaming-pipeline.md](./04-streaming-pipeline.md).
Fix: chunk-based pipeline — process N=50k comics through all
phases, then start the next chunk. Bigger refactor; deferred.

### SQLite write throughput

The importer doesn't pin SQLite PRAGMAs for bulk-write mode.
`journal_mode=WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`,
`mmap_size`, `cache_size` all matter for bulk ingest.

Plus: each `bulk_create` / `bulk_update` runs in its own
auto-commit transaction. Wrapping a phase's worth of inserts in
one `transaction.atomic()` block reduces fsync overhead but
risks blocking readers (browser viewing) for the duration.

Detailed in [05-sqlite-tuning.md](./05-sqlite-tuning.md).

### Comicbox-side wins

`_USED_COMICBOX_FIELDS` in `read/aggregate_path.py:26-76` lists
44 fields codex actually consumes. Comicbox's `to_dict()` returns
all fields it knows about (probably 60+) and codex pops the
unused ones. Field projection (pass the wanted-set into comicbox,
have it skip parsing the rest) would reduce both parse time AND
the pickled dict size crossing the subprocess boundary.

Detailed in [06-comicbox-side.md](./06-comicbox-side.md).

## Sub-plans

Each sub-plan is sized to be one PR. Order is by impact-per-LOC,
with structural risk increasing toward the end:

1. **[01-link-batching.md](./01-link-batching.md)** — millions of
   SELECTs → tens of SELECTs. Self-contained in `link/prepare.py`.
   Highest single-finding impact. Touches `link/prepare.py` and
   adds a name→pk batch helper.
2. **[02-create-fk-batching.md](./02-create-fk-batching.md)** —
   per-row FK SELECTs in create/update phases. Self-contained in
   `create/foreign_keys.py`.
3. **[03-query-prune.md](./03-query-prune.md)** — `query/links_m2m.py`,
   `query/links_fk.py`, `moved/comics.py`. Per-comic M2M / FK
   walks → batch-by-model.
4. **[05-sqlite-tuning.md](./05-sqlite-tuning.md)** — PRAGMAs
   for bulk ingest, transaction batching. Small diff, broad
   impact, low correctness risk if scoped carefully.
5. **[06-comicbox-side.md](./06-comicbox-side.md)** — comicbox
   field projection, lazy parsing, pickle minimization. Touches
   the comicbox repo (user's primary consumer ⇒ safe to modify).
6. **[04-streaming-pipeline.md](./04-streaming-pipeline.md)** —
   chunk-based pipeline. Bigger refactor; lands LAST so the
   smaller wins prove out the perf model first.

## Methodology

For every finding:

1. **Build the perf harness.** No `tests/perf/run_importer_baseline.py`
   exists. Cheap version:
   ```python
   # tests/perf/run_importer_baseline.py
   # Spin up a dev DB with N=10k / 100k / 600k comic fixtures
   # Capture wall clock + per-phase wall clock + query count
   # Run before + after each fix
   ```
   Each sub-plan includes the relevant phase's expected query
   delta.

2. **Capture cold + warm baseline** before any change. The user
   has already optimized; trust the existing numbers as the
   benchmark to beat.

3. **Apply the fix in isolation.** One sub-plan = one PR.

4. **Verify correctness via diff against pre-fix DB state.**
   ```sql
   -- Compare the post-import DB state byte-for-byte where possible
   -- e.g. dump (pk, key_columns, m2m_through_rows) per Comic
   -- and diff before/after
   ```
   For non-trivial perf changes (e.g. chunking the pipeline),
   correctness verification is the gate.

5. **Re-capture baseline.** Document delta in the commit message.

6. **Roll forward to the next finding.**

## Correctness invariants to preserve

The user explicitly emphasized correctness. Things this project
must NOT change without flagging:

- **Comic.unique_together = (library, path)**: every Comic row
  is keyed by (library, full path).
- **FK row identity**: e.g. Publisher rows are unique on
  `name`. Imprint on `(publisher_id, name)`. Series on
  `(publisher_id, imprint_id, name)`. The current code relies
  on these identities for `update_conflicts=True` UPSERTs.
- **M2M through-row uniqueness**: e.g. `(comic_id, character_id)`
  in the through table is unique. The link phase's
  `bulk_create(update_conflicts=True, unique_fields=...)`
  relies on this.
- **Watermark for FTS sync**: a comic update bumps
  `Comic.updated_at` so the FTS sync's watermark logic catches
  it. Any restructure that bypasses `Comic.save()` must still
  bump the timestamp.
- **Deletion cascades**: `Comic` deletion cascades to bookmarks,
  FTS rows, etc. via `on_delete=CASCADE`. Don't bypass.
- **Failed imports record path + reason**: bulk failures must
  still produce per-path FailedImport rows so the admin UI can
  surface them.

Each sub-plan calls out the invariants its change touches.

## Risks

- **Memory regression**. Several findings batch lookups into
  Python dicts (e.g. `dict[(model, name) → pk]`). For an import
  with millions of unique tag names, the dict might grow large.
  Sub-plans cap dict sizes via batched lookups.
- **Database write contention**. The importer writes; the
  browser reads. Long transactions (under [05-sqlite-tuning.md])
  can block readers. Each sub-plan's transaction scope is
  documented.
- **Subprocess pickling cost regression**. [06-comicbox-side.md]
  proposes more transformation INSIDE the subprocess. If that
  transformation itself is slow, the win is offset.
- **Reordering correctness**. The current pipeline order is
  load-bearing — `query` runs before `create_and_update` because
  the latter consumes the former's `CREATE_FKS` / `UPDATE_FKS`
  output. Sub-plans that touch ordering (esp.
  [04-streaming-pipeline.md]) must preserve dependency order
  within each chunk.

## Out of scope

- **Frontend import-progress UX**. Read-side concern; importer's
  status_controller already broadcasts.
- **Library polling logic** (`fs/poller`). Different subsystem.
- **Comicbox's own parser internals beyond the codex-facing API**.
  [06-comicbox-side.md] focuses on the API contract; deeper
  parser refactors live in comicbox's own backlog.
- **Background OPTIMIZE / VACUUM scheduling** outside import. The
  janitor handles those.
- **Cover generation** during import. Already parallelized by
  PR #622.
- **FTS sync** as the import's last phase. Covered by PR #626's
  search-perf project (in flight).

## References

- `codex/librarian/scribe/importer/importer.py:5-15` — pipeline
  ordering
- `codex/librarian/scribe/importer/init.py` — `Counts`,
  filesystem-wait, status init
- `codex/librarian/scribe/importer/const.py` — metadata dict
  keys (data flow)
- `comicbox/process.py:100-146` — `iter_process_files`, the
  read-phase parallelizer (already using `ProcessPoolExecutor`)
- PR #615 (OPDS v2 batching) — reference for the per-M2M
  batching pattern several sub-plans mirror
- PR #626 (search-perf in flight) — same per-M2M batching
  applied to FTS sync
