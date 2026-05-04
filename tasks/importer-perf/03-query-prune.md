# 03 — Query / moved phase batching

Two adjacent issues in the **query** and **moved** phases. The
moved-comics N+1 is the surgical win; the prune-phase memory
profile is a softer concern that becomes a real problem only at
the 600k-comic ceiling.

## Hot path A: per-moved-comic Folder SELECTs

`moved/comics.py:60-68` — `_prepare_moved_comic`:

```python
def _prepare_moved_comic(
    self, comic, folder_m2m_links, updated_comics, del_folder_rows
) -> None:
    try:
        new_path = self.task.files_moved[comic.path]
        old_folder_pks = frozenset(folder.pk for folder in comic.folders.all())
        comic.path = new_path
        new_path = Path(new_path)
        comic.parent_folder = Folder.objects.get(path=new_path.parent)  # ← N+1
        comic.updated_at = Now()
        comic.presave()
        new_folder_pks = frozenset(
            Folder.objects.filter(path__in=new_path.parents).values_list(  # ← N+1
                "pk", flat=True
            )
        )
        ...
```

For every moved comic:

- 1 `Folder.objects.get(path=new_path.parent)` — fetch the new
  parent folder pk.
- 1 `Folder.objects.filter(path__in=new_path.parents)` — fetch
  every ancestor folder pk for the M2M `folders` rebuild.

For a library reorg moving 600k comics: **~1.2M SELECTs** in this
phase alone. Folders are typically a small set
(~10k–50k rows for a deep library), so every one of those SELECTs
touches a single small table that fits in cache, but the round-trip
overhead dominates.

## Fix sketch A: pre-fetch the Folder pk-by-path map

`_bulk_comics_moved_ensure_folders` (called at line 109,
immediately before `_bulk_comics_move_prepare`) already guarantees
every needed Folder row exists. So at the point we enter the prepare
loop, every parent and ancestor folder is in the DB.

Build the path → pk map once:

```python
def _bulk_comics_move_prepare(self) -> tuple[list, dict, dict]:
    """Prepare Update Comics."""
    # All parent/ancestor folders for moved paths exist by now —
    # ``_bulk_comics_moved_ensure_folders`` ran first. Pre-fetch
    # the pk-by-path map once so the per-comic loop is dict lookups.
    folder_pk_by_path = dict(
        Folder.objects.filter(library=self.library).values_list("path", "pk")
    )

    comics = (
        Comic.objects.prefetch_related(FOLDERS_FIELD_NAME)
        .filter(library=self.library, path__in=self.task.files_moved.keys())
        .only(PATH_FIELD_NAME, PARENT_FOLDER_FIELD_NAME, FOLDERS_FIELD_NAME)
    )

    folder_m2m_links = {}
    updated_comics = []
    del_folder_rows = []
    for comic in comics:
        self._prepare_moved_comic(
            comic, folder_pk_by_path,
            folder_m2m_links, updated_comics, del_folder_rows,
        )
    ...
```

Refactor `_prepare_moved_comic` to dict-lookup:

```python
def _prepare_moved_comic(
    self, comic, folder_pk_by_path,
    folder_m2m_links, updated_comics, del_folder_rows,
) -> None:
    try:
        new_path_str = self.task.files_moved[comic.path]
        old_folder_pks = frozenset(folder.pk for folder in comic.folders.all())
        comic.path = new_path_str
        new_path = Path(new_path_str)
        # Was: Folder.objects.get(path=new_path.parent)
        comic.parent_folder_id = folder_pk_by_path[str(new_path.parent)]
        comic.updated_at = Now()
        comic.presave()
        # Was: Folder.objects.filter(path__in=new_path.parents).values_list(...)
        new_folder_pks = frozenset(
            pk for parent in new_path.parents
            if (pk := folder_pk_by_path.get(str(parent))) is not None
        )
        folder_m2m_links[comic.pk] = new_folder_pks
        updated_comics.append(comic)
        if del_folder_pks := old_folder_pks - new_folder_pks:
            for pk in del_folder_pks:
                del_folder_rows.append((comic.pk, pk))
    except Exception:
        self.log.exception(f"moving {comic.path}")
```

**Memory cost**: a Folder pk-by-path map with 50k rows × ~120
bytes/entry = ~6MB. Negligible.

**Query count**:

| | per phase |
| --- | --- |
| **Before** | 2 SELECTs × 600k moves = ~1.2M |
| **After** | 1 SELECT (folder_pk_by_path) + 1 (Comic prefetch) = 2 |

## Hot path B: prune-phase memory pressure

`query/links_m2m.py:85-92` — `_query_prune_comic_m2m_links_batch`:

```python
comics = (
    Comic.objects.filter(library=self.library, path__in=paths)
    .prefetch_related(*COMIC_M2M_FIELD_NAMES)
    .only(*COMIC_M2M_FIELD_NAMES)
)
for comic in comics.iterator(chunk_size=IMPORTER_LINK_M2M_BATCH_SIZE):
    self._query_prune_comic_m2m_links_comic(comic, status)
```

`COMIC_M2M_FIELD_NAMES` resolves to **all 14 M2Ms on Comic**:
`characters`, `credits`, `genres`, `identifiers`, `locations`,
`series_groups`, `stories`, `story_arc_numbers`, `tags`, `teams`,
`universes`, `folders`, `sources`, `tagger`. The
`prefetch_related` fires 14 IN-queries pulling every through-row
for every comic in the batch — even M2Ms the import doesn't
touch.

For an import where most comics only set `credits` and `tags`,
this loads ~12 M2Ms worth of through-rows that get walked,
compared to nothing, and discarded.

Per-comic over a 600k import: at ~5 through-rows per M2M average
× 14 M2Ms = ~70 row-objects materialized per comic. **42M
through-row instances** loaded across the prune phase. Each
through-row carries a fk to the named model that
`_m2m_obj_to_key_tuple` then dereferences (using the prefetch
cache, so no extra SQL — but the in-memory object graph is
sizable).

This isn't a SQL count problem; it's a Python heap problem.

### Fix sketch B: narrow the prefetch to fields actually proposed

The set of M2M field_names actually present in `LINK_M2MS` is
known at the start of the prune phase. Pull that set up-front and
use it as the prefetch list:

```python
def query_prune_comic_m2m_links(self, status) -> None:
    status.subtitle = "Many to Many"
    self.status_controller.update(status)

    # Determine the M2M fields actually referenced this import.
    # Most imports touch credits/tags/characters but skip e.g.
    # universes/sources entirely.
    referenced_field_names: set[str] = set()
    for path_link in self.metadata[LINK_M2MS].values():
        referenced_field_names.update(path_link.keys())
    if not referenced_field_names:
        return
    prefetch_fields = tuple(
        name for name in COMIC_M2M_FIELD_NAMES if name in referenced_field_names
    )

    paths = tuple(self.metadata[LINK_M2MS].keys())
    for start in range(0, len(paths), IMPORTER_LINK_FK_BATCH_SIZE):
        if self.abort_event.is_set():
            return
        batch_paths = paths[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
        self._query_prune_comic_m2m_links_batch(
            batch_paths, prefetch_fields, status
        )
    ...

def _query_prune_comic_m2m_links_batch(
    self, paths: tuple[str, ...], prefetch_fields: tuple[str, ...], status
) -> None:
    comics = (
        Comic.objects.filter(library=self.library, path__in=paths)
        .prefetch_related(*prefetch_fields)
        .only(*prefetch_fields)
    )
    for comic in comics.iterator(chunk_size=IMPORTER_LINK_M2M_BATCH_SIZE):
        self._query_prune_comic_m2m_links_comic(comic, status)
```

For the typical import (credits + tags + a few groups), this drops
from 14 prefetch IN-queries to 3-5. Memory drops proportionally.

The same trick works for `query/links_fk.py:85-89`:

```python
comics = (
    Comic.objects.filter(library=self.library, path__in=batch_paths)
    .select_related(*COMIC_FK_FIELD_NAMES)
    .only(*_QUERY_LINK_FK_PRUNE_ONLY)
)
```

`select_related(*COMIC_FK_FIELD_NAMES)` joins **every** FK on
Comic. For prune purposes, only fields present in
`LINK_FKS[path]` need joining. Compute the union of needed FKs
once per import and narrow the join:

```python
referenced_fks: set[str] = set()
for path_link in self.metadata[LINK_FKS].values():
    referenced_fks.update(path_link.keys())
select_fields = tuple(
    name for name in COMIC_FK_FIELD_NAMES if name in referenced_fks
)
```

For an import that only touches `volume` + `parent_folder`, this
drops from a 12-table JOIN to a 3-table JOIN. SQLite's planner
handles wide joins, but each row still pays the column-decode
cost in the cursor.

## Hot path C: status update call overhead in the prune loops

`query/links_m2m.py:71-72`:

```python
for m2m_obj in m2m_objs:
    deleted |= self._query_prune_comic_m2m_links_field_obj(...)
    status.increment_complete()
    self.status_controller.update(status)  # ← per through-row
```

`status_controller.update()` is rate-limited internally
(`_UPDATE_DELTA = 5s`), so it's mostly a cheap `monotonic()` call
+ early return. But for 42M iterations, even the 50ns guard adds
up to ~2 seconds wasted.

Same shape at `query/links_fk.py:77-78`:

```python
for field_name in field_names:
    self._query_prune_comic_fk_links_field(comic, path, field_name)
    status.increment_complete()
    self.status_controller.update(status)  # ← per FK field
```

### Fix sketch C: hoist the update out of the inner loop

```python
# Inside _query_prune_comic_m2m_links_field
for m2m_obj in m2m_objs:
    deleted |= self._query_prune_comic_m2m_links_field_obj(...)
    status.increment_complete()
# Call update once per field, not per m2m_obj.
self.status_controller.update(status)
```

The progress bar's resolution drops from per-row to per-field, but
the status itself only refreshes every 5s anyway, so user-visible
behavior is unchanged.

## Correctness invariants

- **Folder lookup keys**: `_bulk_comics_moved_ensure_folders` runs
  first and populates `Folder` rows for every parent of a moved
  path. The pk-by-path map is therefore complete by the time the
  prepare loop runs. `Path(...).parents` yields the same string
  values used as `Folder.path`, so the dict lookup is exact.
- **Library scope**: the existing
  `Folder.objects.get(path=new_path.parent)` does **not** filter
  by library — folders are unique by path globally. The fix
  preserves this if we drop `library=self.library` from the pk-map
  query, OR tightens it (Folder rows are library-scoped in the
  schema; verify in `models/groups.py`). **Verify before
  shipping.**
- **Narrowed prefetch**: dropping unused M2Ms from the prefetch
  list is safe because the prune loop only walks `field_names =
  tuple(self.metadata[LINK_M2MS][comic.path].keys())` — never the
  full COMIC_M2M_FIELD_NAMES.
- **Status counter**: hoisting the `update()` out of the inner
  loop preserves `increment_complete()` per row, so the eventual
  `complete` value is identical. Only the refresh cadence changes.

## Risks

- **Folder library scoping**: confirm whether
  `Folder.objects.filter(library=self.library)` is correct or
  whether the model is library-global. The current `get(path=...)`
  is not library-scoped, which could be a latent bug. Resolve
  before flipping to the dict lookup.
- **`only(...)` interaction**: `prefetch_related` ignores `only`
  on the prefetched relation; only the parent's columns are
  narrowed. Already the case in current code.
- **Empty `LINK_M2MS`**: if `referenced_field_names` is empty,
  `prefetch_fields = ()` is passed. Django's `prefetch_related()`
  with no args is a noop. Safe.
- **`COMIC_M2M_FIELDS` vs prefetch ordering**: the existing code
  passes the constant list as positional args to `prefetch_related`.
  Order doesn't matter to Django, but tests pinning queryset SQL
  may break — verify by reading `tests/librarian/scribe/`.

## Suggested commit shape

Three small commits, one PR — each independently revertable:

1. `moved: pre-fetch Folder pk map for moved comic prepare`
   (~30 LOC, biggest measurable win)
2. `query: narrow select_related/prefetch_related to referenced fields`
   (~40 LOC, memory-only win)
3. `query: hoist status update out of M2M-row inner loop`
   (~15 LOC, microoptimization)

Total ~85 LOC. Touches `moved/comics.py`, `query/links_fk.py`,
`query/links_m2m.py`. No schema implications.

## Query count

| Hot path | Before | After |
| --- | --- | --- |
| Moved (600k moves) | ~1.2M SELECTs | 2 SELECTs |
| Prune M2M (600k comics) | 14 IN-queries × N batches | 3-5 IN-queries × N batches |
| Prune FK (600k comics) | 12-table JOIN × N batches | 3-table JOIN × N batches |

## Test plan

- **Move round-trip**: fixture with 1000 comics moved across 50
  folders. Assert resulting `parent_folder_id` and `folders` M2M
  rows are bit-identical between old and new code.
- **Folder-pk-map cache freshness**: regression test that exercises
  `_bulk_comics_moved_ensure_folders` creating a brand-new folder
  mid-move. Confirm that folder appears in the pk map (the map
  is built **after** ensure_folders, so this should hold).
- **Narrowed prefetch correctness**: unit test that runs the
  prune phase with `LINK_M2MS` containing only `credits` and
  `tags`. Assert the resulting `DELETE_M2MS` and `LINK_M2MS`
  contents match the wide-prefetch baseline.
- **Wall clock**: on a 10k-comic dev fixture with 50% rename
  rate, expect the moved phase to drop from O(seconds) to O(ms).
