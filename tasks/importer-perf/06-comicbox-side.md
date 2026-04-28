# 06 — Comicbox-side improvements

The user owns comicbox and codex is its primary consumer, so
upstream changes are fair game. Most of the win is in eliminating
wasted work that codex throws away anyway.

The cross-process boundary is the dominant cost: every comic's
metadata dict is pickled in the worker, sent through a pipe,
unpickled in the importer. Anything that shrinks or skips that
dict is leveraged across 600k comics.

## Boundary map

```
┌──────────────────┐  pickle      ┌──────────────────┐
│ codex importer   │ ◄─────────── │ comicbox worker  │
│  ExtractStep     │              │  _read_one       │
│  ↓               │              │  ↓               │
│  filters md      │              │  cb.to_dict()    │
│  ↓               │              │  ↓               │
│  uses ~44 fields │              │  builds full md  │
└──────────────────┘              └──────────────────┘
```

Two waste streams:

1. **Worker compute waste**: `cb.to_dict()` parses + normalizes
   *every* metadata key the source format exposes (CIX, CBI, CIL,
   filename heuristics, etc.). Codex's
   `_USED_COMICBOX_FIELDS` (`read/aggregate_path.py:26-76`) lists
   ~44 keys. The remaining keys (`alternate_images`, `bookmark`,
   `pages`, `prices`, `remainders`, `reprints`, `rights`,
   `updated_at`, `ext`, `credit_primaries`,
   `identifier_primary_source`, …) are computed and immediately
   discarded.

2. **Cross-process pickle waste**: the discarded keys travel
   through the pipe before being dropped. For a metadata-rich
   tagged CBR with `pages: [...]` enumerating every page's
   filename + bookmark state, the dict can hit 50-100 KB. At 600k
   comics, that's **30-60 GB** of pickle traffic for data the
   importer never reads.

## Improvement A: field projection in `comicbox.box.to_dict()`

Add a `keys` parameter that limits the returned dict to the
requested keys, skipping computation of the rest where possible.

```python
# comicbox/box/__init__.py (sketch)
def to_dict(
    self,
    keys: Collection[str] | None = None,
    *,
    embed_pages: bool = True,
) -> dict:
    """Return normalized metadata. ``keys`` filters output keys
    and skips upstream parse stages for keys nothing depends on.
    """
    ...
```

The interesting bit isn't the filter (codex can do that itself);
it's **skipping the parse work** for unrequested keys. Some
examples of work that disappears when keys are pruned:

- `pages: [...]`: parsing the per-page list from CIX requires
  walking every `<Page>` element. If `pages` isn't in `keys`,
  skip the walk.
- `alternate_images`: requires re-scanning the archive directory
  for matching filenames. Skip if not requested.
- `credit_primaries`: a derived field requiring a second pass
  over `credits`. Skip if not requested.

For codex, the `keys` set is the existing `_USED_COMICBOX_FIELDS`
constant. Pass it through:

```python
# codex/librarian/scribe/importer/read/extract.py
md = cb.to_dict(keys=_USED_COMICBOX_FIELDS)
```

### Estimated impact

Hard to predict without profiling comicbox's parse pipeline. Order
of magnitude: a tagged CBR with 100-page archives spends ~30-50%
of its parse time on `pages` enumeration. Dropping `pages` alone
halves the per-comic work for richly-tagged libraries. Across
600k comics this is hours, not minutes.

### Risks

- **API change**: `to_dict()` is a public method. Add the
  parameter with a default that preserves current behavior
  (`keys=None` returns all keys).
- **Parser graph**: comicbox parsers form a graph where some
  outputs depend on others' intermediates. Cutting an output may
  not cut its compute if other outputs need its parser. Track
  per-key parse dependencies so the skip is honored only when
  *no* requested key needs the parser. Practical implementation:
  start with a hand-curated allowlist of fields safe to skip
  (`pages`, `alternate_images`, `bookmark`, `prices`).

## Improvement B: caller-supplied "skip if unchanged" map

Codex already drops `page_count` and `file_type` from the
returned dict if they match the previous values
(`extract.py:88-91`). Comicbox could accept a `skip_if_equal`
mapping and do the same in-worker, before pickling:

```python
# comicbox/process.py
def _read_one(
    path,
    config=None,
    fmt=...,
    old_mtime=None,
    *,
    full_metadata: bool = True,
    skip_if_equal: Mapping[str, Any] | None = None,  # NEW
) -> dict:
    ...
    md = cb.to_dict(...)
    if skip_if_equal:
        for key, prior in skip_if_equal.items():
            if md.get(key) == prior:
                md.pop(key, None)
    return md
```

Codex already has `all_old_comic_values` keyed by path. Pass it
through `iter_process_files` so each worker can drop unchanged
fields before pickling:

```python
for path, value in iter_process_files(
    all_paths,
    config=COMICBOX_CONFIG,
    logger=self.log,
    old_mtime_map=all_old_comic_mtimes,
    skip_if_equal_map=all_old_comic_values,  # NEW
    full_metadata=import_metadata,
):
```

### Estimated impact

Page-count and file-type are 2 small keys, so the immediate
pickle savings are minor. The win is *structural*: it makes
comicbox aware of the "what's already in the DB" concept, which
opens the door to bigger wins (skip parsing tag fields where
ComicInfo.xml hasn't changed, etc.).

Skip this one if the structural shift isn't worth the API churn.
Marked optional.

## Improvement C: `MetadataFormats` union flag for fast-path tagged-only reads

Most modern libraries are pure-CIX (ComicRack ComicInfo.xml).
Comicbox tries every format
(`MetadataFormats.COMICBOX_YAML` is the union of all formats).
For a CIX-only library, the CBI, CIL, COMET, ComicTagger, and
filename heuristic parsers run, find nothing, and return empty.

Allow the caller to pin the parse to a single format:

```python
# Already exists at the API level — codex passes
# MetadataFormats.COMICBOX_YAML to iter_process_files. Just need a
# narrower default:
fmt = MetadataFormats.COMIC_INFO  # CIX only

for path, value in iter_process_files(paths, fmt=fmt, ...):
    ...
```

But the format is a per-archive property, not a per-library one.
A library could be a mix of CBZ (CIX) and CBR (CBI). Idea:
**probe-and-cache** per-library — first 50 archives use the full
union, then fix the format to whichever was hit. Risky if the
user adds a CBR mid-import.

Better: a comicbox-side **early-out** when the cheap parse hits.
Try CIX first (it's the cheap one); if it returns a non-empty
dict, skip CBI / CIL / heuristic parsers entirely. Only fall back
to the union when CIX comes up empty.

```python
# comicbox/box/__init__.py (sketch)
_PRIMARY_FORMATS = (
    MetadataFormats.COMIC_INFO,
    MetadataFormats.METRON_INFO,
)

def to_dict(self, ...) -> dict:
    for fmt in _PRIMARY_FORMATS:
        if md := self._parse_one_format(fmt):
            return self._normalize(md)
    # All cheap formats came up empty — try the full union.
    return self._parse_full_union()
```

### Estimated impact

For a fully-CIX library (~95% of real-world cases), maybe **30%
shorter per-comic parse**. The gain compounds with field
projection from improvement A.

### Risks

- A library where some files have CBI and others have CIX would
  see CIX-tagged files miss CBI-only data. Acceptable: if CIX
  exists, CBI is supplementary. Behavior matches user intuition.

## Improvement D: skip archive open when filesystem mtime is stale

`extract.py:135-140` passes `old_mtime_map` so workers can skip
re-extracting metadata when the file's metadata hasn't changed.
But the worker still **opens the archive** to call
`cb.get_metadata_mtime()`:

```python
# comicbox/process.py:46-61
def _read_one(...):
    md = {}
    with Comicbox(path, config=config, fmt=fmt) as cb:
        if full_metadata:
            if not old_mtime:
                md = cb.to_dict()
                ...
            else:
                new_md_mtime = cb.get_metadata_mtime()
                if not new_md_mtime or new_md_mtime > old_mtime:
                    md = cb.to_dict()
                    ...
        if "page_count" not in md:
            md["page_count"] = cb.get_page_count()
        ...
```

Even when `new_md_mtime <= old_mtime`, the worker has already
paid the archive-open cost. That cost is non-trivial — for CBR
the rarfile lib spawns `unrar` and parses headers; for CBZ
there's a central directory read.

Idea: **filesystem mtime gate** before submitting. Codex already
has `task.check_metadata_mtime` and `old_mtime_map`. Compare the
file's `os.stat().st_mtime` against `old_mtime` in the *parent*
process. Only submit if newer.

```python
# In codex/.../extract.py, before iter_process_files
to_submit = []
for path in all_paths:
    old_mtime = all_old_comic_mtimes.get(path)
    if old_mtime is None:
        to_submit.append(path)
        continue
    fs_mtime = datetime.fromtimestamp(Path(path).stat().st_mtime, tz=UTC)
    if fs_mtime > old_mtime:
        to_submit.append(path)
    # else: skip — file unchanged on disk
```

Catch: filesystem mtime is the **archive file's** mtime, not the
**embedded ComicInfo.xml's** mtime. A user re-saving the same
ComicInfo.xml back into the archive bumps the file mtime even if
the embedded mtime didn't change. False positives only — never
false negatives — so this is a pure win, just not as big a win as
the embedded check.

For a re-import where 99% of files are unchanged, this drops the
worker submit count from 600k to ~6k. **Massive**.

### Risk

The codex `task.check_metadata_mtime` flag is documented as
honoring the *embedded* mtime. A filesystem-level pre-filter is
strictly stricter — files that pass the filesystem check still go
through the embedded check downstream. So the user-visible
guarantee tightens, never loosens. Document the change.

## Improvement E: `fork` startup on Linux

`ProcessPoolExecutor` defaults to `spawn` on macOS (3.8+) and
defaults to whatever the platform default is on Linux (currently
`fork`, switching to `spawn` in 3.14+ pending PEP 711).

For codex's import workload, `fork` is much cheaper at startup —
no re-import of comicbox + codex + Django. With `spawn` and 600k
comics, the 4-8 worker processes import the world once each,
roughly 200-500 ms × num_workers of dead time at the start.

Force `fork` on Linux:

```python
# comicbox/process.py
import multiprocessing as mp

def iter_process_files(...):
    ctx = mp.get_context("fork") if sys.platform == "linux" else None
    executor = ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx)
```

### Risk

`fork` after threads are running is unsafe. Codex's importer runs
inside a daemon thread (`ScribeThread`) — by the time
`iter_process_files` is called, the parent process has multiple
threads (the librarian threads, Granian's worker threads, etc.).
A forked child inherits those threads' state, including held
locks. SQLite's threading model in particular is hostile to
post-fork.

So **safe fork is conditional** on closing the SQLite connection
+ stopping accepts before fork, then restarting after. Risky
infrastructure change.

**Recommendation**: skip improvement E unless a specific
benchmark proves the spawn overhead is on the critical path. The
600k-comic startup cost amortizes to negligible across the import
duration.

## Improvement F: per-worker comicbox instance pooling

Each `_read_one` call constructs a fresh `Comicbox(path, config,
fmt)` and runs `__enter__` / `__exit__`. The Comicbox class's
init does parser registration, config validation, etc. For a
worker that processes hundreds of files in its lifetime, this
init runs hundreds of times.

Cache the parser registry at worker module import time:

```python
# comicbox/box/__init__.py
@lru_cache(maxsize=1)
def _build_parser_registry():
    """Build the parser registry once per worker process."""
    return {...}

class Comicbox:
    def __init__(self, ...):
        self._parsers = _build_parser_registry()
        ...
```

### Estimated impact

Modest. The init was probably already cheap. Worth reading the
comicbox profile before chasing this.

## Suggested commit shape (comicbox repo)

Three small PRs against comicbox, each independent:

1. **`feat: to_dict(keys=...)` field projection** — additive API,
   default behavior unchanged. ~150 LOC + parser dependency map.
2. **`feat: probe primary formats first` (improvement C)** — pure
   internal optimization, no API change. ~50 LOC.
3. **`docs: filesystem mtime pre-filter recommendation`** — codex-
   side change, no comicbox change required. Just document the
   pattern in the comicbox README so other consumers benefit.

## Suggested commit shape (codex repo)

One PR after comicbox PRs land:

1. Wire `keys=_USED_COMICBOX_FIELDS` through to `to_dict`.
2. Add filesystem-mtime pre-filter in `extract.py` ahead of
   `iter_process_files`.

~30 LOC. Touches `read/extract.py` and bumps the comicbox
dependency floor.

## Correctness invariants

- **Field projection completeness**: `_USED_COMICBOX_FIELDS` must
  be a superset of every key codex actually reads. Audit the
  importer for `md.get(...)` and `md["..."]` accesses; assert
  every key referenced is in the set.
- **Probe order**: CIX-first probe must not lose CBI-only data.
  For a CBI-tagged-only file, the CIX probe returns empty and the
  fallback union runs. Test fixture: a CBR with only CBI metadata.
- **Filesystem mtime monotonicity**: the parent's `Path.stat()`
  result must be a `datetime` in UTC matching the worker's
  `cb.get_metadata_mtime()` timezone. The current code converts
  to UTC at `extract.py:42-46`; mirror that conversion in the
  pre-filter.
- **Skip-if-equal payload identity**: `md.get(key) == prior`
  comparison uses `==` semantics. For nested types (lists,
  dicts), Python's deep equality is correct. For datetimes,
  timezone-aware vs naive comparison must match — already a
  concern in `extract.py`.

## Risks

- **Comicbox API stability**: codex pins comicbox to a version.
  Any cross-cutting comicbox PR forces a codex compatibility
  bump. Coordinate the PR sequence.
- **Pickle compat**: changing `_read_one`'s signature breaks
  in-flight workers across a comicbox upgrade. Stage rollouts so
  importer is fully restarted before new comicbox code runs.
- **Field projection misses unknown deps**: a future codex
  feature reads a key not in `_USED_COMICBOX_FIELDS`. The field
  projection silently returns nothing. Mitigation: define the
  field set as a strict TypedDict or dataclass on the codex side
  so the linter catches missing fields.

## Test plan

- **Field projection round-trip**: `to_dict(keys=USED)` on a
  fixture comic returns a dict whose keys equal `USED ∩
  available_keys`. No extra, no missing.
- **Pickle size regression**: snapshot the pickled-byte size of a
  representative tagged CBR before/after field projection. Assert
  ≥ 30% reduction.
- **Probe-first correctness**: fixture CBR with CBI-only metadata
  parses correctly under improvement C.
- **Filesystem pre-filter**: integration test with 1000 unchanged
  comics + 10 modified. Assert only 10 are submitted to
  `iter_process_files`.
- **Wall-clock**: 10k-comic dev fixture, full re-import (no
  changes). Expect ≥ 80% time reduction (most comics short-circuit
  via filesystem-mtime gate).

## Out of scope (but worth noting)

- **Comicbox async API**: `aread_metadata` exists but isn't used
  by the importer. Async + `asyncio.gather` could replace the
  ProcessPool for I/O-bound parses, with lower overhead than
  cross-process. Worth benchmarking but a much larger change.
- **Streaming archive open**: comicbox currently opens the full
  archive central directory. For 1k-page archives this is heavy.
  A "metadata-only" archive open mode (read just enough to find
  ComicInfo.xml, then bail) would help. Speculative; would
  require rarfile / zipfile / py7zr cooperation.
