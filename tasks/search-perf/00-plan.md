# Search indexer perf — plan

`codex/librarian/scribe/search/` is small (8 files, ~750 LOC) —
single plan file, no meta split.

## Why this matters

The search indexer rebuilds the SQLite FTS5 virtual table that
powers the browser's search box. On a fresh import — and
periodically thereafter — it walks the whole `Comic` table,
joining ~10 FK columns and aggregating ~10 M2M relations into a
denormalized text-search row per comic. On a 100k-comic library
that's a multi-minute stall during which the user sees no search
results for newly-imported books.

The user noted: "it's very slow but I'm not sure if that's
avoidable." Some of it is — FTS5 token re-indexing is what it is.
But the audit surfaces three categories of waste that are very
much avoidable:

1. A whole branch of dead `prefetch_related` calls that fire
   nothing at runtime.
2. A megaquery pattern (10 `GROUP_CONCAT` aggregates + 10 LEFT
   JOIN'd FK columns in one SELECT) where SQLite materializes a
   huge join cardinality before collapsing.
3. **Three column-name mismatches** between the annotation aliases
   and the Python consumer's expected keys — the DB pays for
   `GROUP_CONCAT(credits__person__name)`, `GROUP_CONCAT(
   identifiers__source__name)`, and `GROUP_CONCAT(
   story_arc_numbers__story_arc__name)` aggregations whose
   results are **silently dropped** by `prepare_sync_fts_entry`,
   because the consumer reads `fts_credits` / `fts_sources` /
   `fts_story_arcs` (without the relation suffix). Pure waste *and*
   the resulting FTS columns are empty — search by credit person /
   source / story arc is broken for sync-built entries.

## Scope

```
codex/librarian/scribe/search/
├── __init__.py
├── const.py        FTS column lists for bulk_update
├── handler.py      Task dispatch
├── optimize.py     FTS5 ``optimize`` SQL
├── prepare.py      ComicFTS entry assembly (consumer of annotations)
├── remove.py       clear / stale-record paths
├── status.py       Status dataclasses
├── sync.py         The hot loop: queryset build + per-batch upsert
└── tasks.py        Task shapes
```

Hot path: `SearchIndexerSync._update_search_index_operate` →
per-batch loop: queryset construction → `.values()` materialization
→ `prepare_sync_fts_entry` per row → `bulk_create` /
`bulk_update`.

## Findings

### F1 — `_prefetch_related_fts_query` is dead code **(refactor)**

`codex/librarian/scribe/search/sync.py:127-145`:

```python
@staticmethod
def _prefetch_related_fts_query(qs):
    # Prefecthing deep relations breaks the 1000 sqlite query depth limit
    return qs.prefetch_related(
        "characters", "credits", "identifiers", "genres", "locations",
        "series_groups", "stories", "story_arc_numbers", "tags", "teams",
        "universes",
    )
```

The hot loop calls this then chains `.values()`:

```python
comics = self._prefetch_related_fts_query(comics)
comics = comics.order_by("pk")
comics = comics[:search_index_batch_size]
comics = self._annotate_fts_query(comics)
for comic in comics.values():
    SearchEntryPrepare.prepare_sync_fts_entry(comic, ...)
```

**Empirically verified**: when a `QuerySet` chains
`prefetch_related(...)` with `.values()`, the prefetches don't
fire — `prefetch_related_objects` walks the result cache looking
for FK descriptors, but a `.values()` queryset's results are
plain `dict`s with no descriptors. Test transcript:

```python
>>> qs1 = Comic.objects.prefetch_related("characters", "credits", "genres").values("pk")
>>> with CaptureQueriesContext(connection) as ctx:
...     list(qs1)
>>> len(ctx.captured_queries)
1   # only the main SELECT — zero prefetch queries
```

The 11 prefetch declarations contribute **zero query work** —
they're pure documentation. The associated comment about "1000
sqlite query depth" is irrelevant since the prefetches don't
actually fire.

**Fix**: drop `_prefetch_related_fts_query` and its single call
site. Remove the `# Prefecthing deep relations breaks the 1000
sqlite query depth limit` comment (no longer applicable —
nothing is being prefetched).

Pure cleanup. Doesn't change behavior or perf, but removes a
significant chunk of misleading code from the hot path.

### F2 — Three FTS column-name mismatches **(correctness + perf)**

`prepare.py:_COMIC_KEYS` lists the keys the consumer reads from
each comic dict:

```python
_COMIC_KEYS = (
    ...,
    "fts_credits",                 # ← this name
    "fts_sources",                 # ← this name
    "fts_story_arcs",              # ← this name
    ...,
)
```

But `sync.py:_M2M_FTS_RELS` produces annotations under different
aliases:

```python
_M2M_FTS_RELS = (
    "characters",
    "credits__person",             # → annotation alias: fts_credits__person
    ...,
    "identifiers__source",         # → fts_identifiers__source
    ...,
    "story_arc_numbers__story_arc",# → fts_story_arc_numbers__story_arc
    ...,
)

_M2M_FTS_ANNOTATIONS = MappingProxyType(
    {f"fts_{rel}": GroupConcat(f"{rel}__name", ...) for rel in _M2M_FTS_RELS}
)
```

So three relations are double-prefixed at the SQL layer
(`fts_credits__person`, `fts_identifiers__source`,
`fts_story_arc_numbers__story_arc`) but the Python consumer
looks for the short name (`fts_credits`, `fts_sources`,
`fts_story_arcs`).

`prepare_sync_fts_entry` then:

```python
entry = {
    key.removeprefix("fts_"): comic.get(key, "")
    for key in _COMIC_KEYS
    if comic.get(key)         # ← filters out missing keys silently
}
```

Three columns silently get empty strings.

**Two failure modes ride this single bug:**

- **Perf waste**: SQLite still computes the three GROUP_CONCAT
  aggregations (with their LEFT JOINs to the M2M tables and a
  GROUP BY collapse). Each is part of the megaquery's
  cartesian-product cost. Pure work that's thrown away.
- **Correctness regression**: the `credits` / `sources` /
  `story_arcs` columns of `codex_comicfts` are empty for any
  comic that arrived via the sync path (not the import path —
  `prepare_import_fts_entry` populates these correctly via
  comicbox payload keys). Searching for a credit-person name,
  identifier source, or story-arc title silently returns no
  results.

The likely history: at some point the M2M rels were renamed to
include the FK suffix (`credits → credits__person`) so the
GROUP_CONCAT walks the right column, but the Python consumer
keys weren't updated.

**Fix sketch**

Reconcile the names. Two options:

(a) **Rename `_M2M_FTS_RELS` to short-name keys and use a
separate map for the GROUP_CONCAT source field.**

```python
_M2M_FTS_REL_MAP = MappingProxyType({
    "characters":        "characters__name",
    "credits":           "credits__person__name",
    "genres":            "genres__name",
    "locations":         "locations__name",
    "series_groups":     "series_groups__name",
    "sources":           "identifiers__source__name",
    "stories":           "stories__name",
    "story_arcs":        "story_arc_numbers__story_arc__name",
    "tags":              "tags__name",
    "teams":             "teams__name",
})

_M2M_FTS_ANNOTATIONS = MappingProxyType({
    f"fts_{alias}": GroupConcat(target, distinct=True, order_by=target)
    for alias, target in _M2M_FTS_REL_MAP.items()
})
```

The annotation alias becomes `fts_credits` / `fts_sources` /
`fts_story_arcs`, matching `_COMIC_KEYS`. Same SQL is generated;
just the alias name changes.

(b) **Add a translation map** in `prepare_sync_fts_entry`. Keeps
the relation-suffix aliases but maps them to the short names at
read time. More code, harder to follow.

Recommendation: **(a)** — single source of truth, simpler call
site.

This is **both a perf fix (3 GROUP_CONCATs whose data is
preserved instead of dropped — same cost, but the data isn't
thrown away)** and a **correctness fix (sync-built FTS entries
get credits / sources / story_arcs populated again).**

The behavior change worth flagging: searches that previously
returned zero results for credit person names / source URN
identifiers / story arc names will start returning hits. Users
who'd worked around the bug by importing via the comicbox path
won't notice. Test before merging.

### F3 — Megaquery vs per-M2M batched queries **(headline perf)**

The `_annotate_fts_query` shape is **one SELECT with**:

- 10 LEFT JOINs to FK tables (publisher, imprint, series,
  age_rating, age_rating__metron, country, language, scan_info,
  tagger, original_format)
- 10 LEFT JOINs to M2M tables × 2 (the through table + the
  named table) = 20 more
- 10 `GROUP_CONCAT(... ORDER BY ... DISTINCT)` aggregations
- `GROUP BY comic.id` to collapse the cartesian product

For a comic with 5 characters, 3 credit-people, 2 genres, 4
tags, etc., the intermediate row count *before* GROUP BY is
`5 × 3 × 2 × 4 × ...` = the cartesian product. SQLite
materializes this temp table, sorts for DISTINCT in each
GROUP_CONCAT, then GROUP BYs to collapse. **Memory + I/O cost
explodes for richly-tagged comics.**

The pattern works for small libraries but scales poorly. On a
100k-comic library with average M2M counts, the temp tables run
into multi-MB territory per batch.

**Fix sketch — the OPDS metadata batching pattern.**

`codex/views/opds/metadata.py:get_m2m_objects_by_comic` already
solves the same problem for OPDS feeds: each M2M relation runs
as its own UNION'd query keyed by `_comic_id`, and Python
stitches the results. No cartesian product; each query is small
and walks one M2M's index.

Apply the same shape to `_update_search_index_operate`:

1. Compute the batch's pk list (single `Comic.objects...
   .values_list("pk", flat=True)[:batch_size]`).
2. Run **one** query for the comic + simple FK columns
   (`select_related` for the 10 FK joins; no M2M, no
   GROUP_CONCAT). Materialize as `dict[pk, fk_columns]`.
3. Run **10** independent queries for each M2M, each shaped:
   `GROUP_CONCAT(<m2m>__name) GROUP BY <m2m>__comic_id`.
   Collect into `dict[pk, m2m_string]` per relation.
4. Stitch the per-pk dicts into the final FTS rows in Python
   (cheap dict merges; no DB).

**Query count**: 1 (FK row) + 10 (M2M aggregates) = 11 queries
per batch instead of 1 megaquery. Sounds worse but each
individual query is far cheaper because there's no cartesian
product. The overall cost is dominated by the M2M index walks,
which are now bounded — `O(M2M-table-rows)` instead of
`O(product of M2M counts per comic × batch size)`.

**Risk**: changes the order of FTS column population. The bulk
update / create still produces the same final ComicFTS rows;
just the intermediate construction looks different. No
search-ranking impact.

This is the **headline perf finding**. The dead-code F1 + the
name-mismatch F2 are easy wins; F3 is the big one for libraries
that the user reports as "very slow."

### F4 — `ComicFTS.objects.exists()` per loop iteration **(small)**

`sync.py:197-201`:

```python
@staticmethod
def _get_operation_comics_query(qs, *, create: bool):
    if create and not ComicFTS.objects.exists():
        qs = Comic.objects.all()
    return qs
```

Called inside the while loop of `_update_search_index_operate`
(lines 215, 241). After iteration 1, `ComicFTS` has rows so
`.exists()` returns True and the branch doesn't fire — but the
SELECT runs every iteration regardless.

**Fix**: hoist the check outside the loop. The "FTS empty"
state is only true at the start of a fresh rebuild; once a
batch lands, it's permanently False for the rest of the run.

```python
def _update_search_index_operate(self, comics_filtered_qs, *, create):
    fts_initially_empty = create and not ComicFTS.objects.exists()
    base_qs = Comic.objects.all() if fts_initially_empty else comics_filtered_qs
    ...
    while start < total_comics:
        ...
        comics = base_qs
        comics = comics.order_by("pk")[:search_index_batch_size]
        comics = self._annotate_fts_query(comics)
        ...
```

Drops one SELECT per iteration. Trivial alongside F3 but worth
bundling.

### F5 — `time()` → `monotonic()` for elapsed_time reporting **(low)**

`sync.py:298, 311`:

```python
start_time = time()
...
elapsed_time = time() - start_time
elapsed = naturaldelta(elapsed_time)
```

Same correctness fix as PR #623 / #624 / etc. Wall-clock jumps
(NTP / DST / manual adjustment) skew the elapsed reporting.

Trivial swap. Bundle with F4.

### F6 — `clear_search_index` slow on FTS5 **(defer)**

`remove.py:16-21`:

```python
def clear_search_index(self) -> None:
    clear_status = SearchIndexClearStatus()
    self.status_controller.start(clear_status)
    ComicFTS.objects.all().delete()
    self.status_controller.finish(clear_status)
```

`QuerySet.delete()` on an FTS5 virtual table:

1. Django fetches all PKs (`SELECT comic_id FROM codex_comicfts`).
2. Issues `DELETE FROM codex_comicfts WHERE comic_id IN (...)`
   in batches of 1000.
3. For each delete, FTS5 walks its term index removing tokens.

For a 100k-row FTS table, this is the slow part of the
"rebuild" path. Two faster alternatives:

(a) **Raw `DELETE FROM codex_comicfts` (no WHERE)** — single
SQL. Django's QuerySet.delete still does the fetch-then-delete
dance even when the filter is empty. Bypass via raw cursor.

(b) **DROP + CREATE the virtual table** — atomic-ish, MUCH
faster than per-row token removal. But requires keeping the
schema definition in sync with the migration; if the FTS5
column list ever changes, this code has to too. Risky.

Recommendation: (a) is safe and simple. (b) is the optimal but
needs careful schema handling.

**Defer until the rebuild path's wall time is the bottleneck.**
For sync (the more common path), F1+F2+F3 dominate.

### F7 — M2M writes don't bump `Comic.updated_at` **(out of scope)**

`Comic.updated_at` is `auto_now=True` from `BaseModel`. Plain
`comic.save()` bumps it. But Django's M2M `.add()` / `.remove()`
operations don't trigger the parent's `auto_now` — they fire
only `m2m_changed` signals.

If a comic's M2M rows change (e.g. a character is added)
without a corresponding `comic.save()`, the comic's
`updated_at` doesn't advance. The FTS sync's watermark logic
(`updated_at__gt=fts_watermark`) won't pick up the change, and
the FTS row goes stale.

**Surface as a separate concern** — fix would touch the
importer / admin paths, not the search indexer. Out of scope
for this perf plan, but worth flagging.

### F8 — Sync via `INSERT INTO codex_comicfts SELECT ...` **(future)**

The fastest possible sync path: do the FTS row construction in
SQL itself. With F2+F3 reconciled, the FTS columns line up with
the Comic + annotation columns; an `INSERT INTO codex_comicfts
(...) SELECT ... FROM codex_comic LEFT JOIN ...` could populate
FTS rows without round-tripping through Python.

This eliminates `prepare_sync_fts_entry` and the
`bulk_create` / `bulk_update` python-side work entirely. SQLite
can ingest the FTS rows directly from the SELECT result.

**Defer** — large rewrite, requires careful raw-SQL
maintenance, and the gains beyond F1+F2+F3 are uncertain
without a baseline.

## Suggested ordering

1. **F1** (dead `prefetch_related`) — pure cleanup, no behavior
   change. Land first; smallest diff.
2. **F2** (column-name mismatches) — correctness + perf. The
   behavior change (sync entries now have credits/sources/
   story_arcs populated) is real; needs a test pass on a
   populated dev DB before merge.
3. **F4 + F5** — small bundle (`exists()` hoist + monotonic
   clock). No behavior change.
4. **F3** (megaquery → per-M2M UNION batches) — the headline
   change. Largest diff, biggest payoff. Land after the
   smaller ones so a regression bisect points at the right
   commit.
5. **F6 / F7 / F8** — deferred. Open follow-up issues.

## Methodology

For each finding:

1. **Capture baseline** — `tests/perf/run_search_baseline.py`
   doesn't exist yet; would need to be added (parallel to
   `run_baseline.py`). Cheap shape: spin up a dev DB with a
   known comic count, fire `SearchIndexSyncTask(rebuild=True)`,
   measure wall time + query count.

2. **Apply the fix**.

3. **Re-run baseline**. F1 should be no-op on query count; F2
   should be no-op on count + populate three previously-empty
   columns; F3 should multiply queries by ~10× per batch but
   reduce wall time by a larger factor (no cartesian product).

4. **Land as one commit per finding** with cold + warm baselines
   in the commit message.

## Verification

- `make test-python` clean across all five fixes.
- After F2: search by a known credit-person name / story-arc
  title / identifier source URN returns hits on a populated
  install. Before F2: those searches returned zero.
- After F3: rebuild wall time on a 100k-library install drops
  noticeably. Pin the new query count via a regression test.
- After F4+F5: no observable behavior change.

## Risks

- **F2 schema/wire change**: search results for credit / source /
  story-arc queries change from "always empty" to "populated".
  Could be perceived as a regression by anyone relying on the
  empty-results behavior. Roll out behind a release note.
- **F3 query reshape**: if the per-M2M UNION batching trips
  some SQLite planner edge case, performance could regress on
  small libraries (where the megaquery is small enough not to
  trigger the cartesian-product blowup). Microbench against a
  range of library sizes (1k / 10k / 100k comics).
- **F6 deferred**: rebuild on FTS5 is genuinely slow due to
  token re-indexing. The bulk INSERT path doesn't help — FTS5
  has to tokenize every row. Token cost is fundamental; don't
  promise wins beyond what F1+F2+F3 deliver for sync.

## Out of scope

- **Search query / ranking**. Read-side. Plan covers the indexer
  only.
- **FTS5 schema changes** (new columns, different tokenizer).
  Independent project.
- **comicbox parser perf** — the import path's slow side is
  comicbox extraction; orthogonal to the indexer.

## References

- `codex/librarian/scribe/search/sync.py` — the hot loop
- `codex/librarian/scribe/search/prepare.py` — the consumer
  with the name mismatches
- `codex/views/opds/metadata.py:get_m2m_objects_by_comic` — the
  per-M2M UNION batching pattern F3 should mirror
- PR #615 (OPDS v2 batching) — same shape applied to OPDS
- PR #623 / #624 — the `time()` → `monotonic()` correctness fix
  applied to other librarian threads
