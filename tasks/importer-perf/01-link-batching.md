# 01 — Link M2M batching

The headline impact-per-LOC finding for the importer. Self-
contained in `link/prepare.py`. Drops millions of SELECTs to
tens.

## Hot path

`link/prepare.py:105-135` — `link_prepare_m2m_links`. Called
once per import after `create_and_update`, before `link`. For
each comic in the batch:

```python
for comic_pk, comic_path in comics:
    md = self.metadata[LINK_M2MS][comic_path]

    # Folders + 3 complex models (Credits, Identifiers, StoryArcNumbers)
    self._link_prepare_complex_m2ms(
        all_m2m_links, md, comic_pk, FOLDERS_FIELD_NAME,
        self._get_link_folders_filter,
    )
    for field_name in COMPLEX_MODEL_FIELD_NAMES:
        self._link_prepare_complex_m2ms(
            all_m2m_links, md, comic_pk, field_name,
            self._get_link_complex_model_filter,
        )

    # Named M2Ms (characters, genres, locations, tags, teams,
    # series_groups, stories — ~7 fields)
    for field, names in md.items():
        self._link_prepare_named_m2ms(all_m2m_links, comic_pk, field, names)
```

`_link_prepare_named_m2ms` (line 83-103):

```python
pks = (
    model.objects.filter(name__in=names).values_list("pk", flat=True).distinct()
)
```

**One SELECT per (comic, M2M field).**

`_link_prepare_complex_m2ms` (line 62-81):

```python
m2m_filter = link_filter_method(field_name, values)
pks = model.objects.filter(m2m_filter).values_list("pk", flat=True).distinct()
```

**One SELECT per (comic, complex M2M field).**

## Per-import cost

Per comic: 4 complex + ~7 named = ~11 SELECTs minimum (more if
the comic has all M2M fields populated).

For the user's 600,000-comic target:
**~6.6 million SELECTs in this phase alone.**

Each SELECT is small (`name IN (...)`) but the round-trip
overhead, query plan compilation, and Python-side ORM dispatch
dominate at this scale. Wall time: estimated 10s of minutes to
hours, depending on hardware.

## Why this happens

The structure assumes per-comic granularity is necessary because
each comic has a *different* set of M2M values. But the LOOKUP
("name → pk") is global — once we know `Character "Wolverine"`
has pk 12345, we can use that pk for every comic that links to
Wolverine.

## Fix sketch

Pre-fetch the name→pk lookup map ONCE per model, before the
per-comic loop. Per-comic work becomes pure dict lookups.

### Step 1: collect all unique names per model up front

```python
def _collect_m2m_names_per_model(
    self, link_m2ms: dict
) -> dict[type[BaseModel], dict[tuple, set[tuple]]]:
    """Walk LINK_M2MS once and collect every (key_tuple) per model.

    Returns ``{model: {key_tuple: set_of_complete_value_tuples}}``
    so the next step can issue one SELECT per model.
    """
    per_model: dict[type[BaseModel], set[tuple]] = {}
    for comic_path, md in link_m2ms.items():
        for field_name, value_tuples in md.items():
            field = Comic._meta.get_field(field_name)
            model = field.related_model
            per_model.setdefault(model, set()).update(value_tuples)
    return per_model
```

### Step 2: one SELECT per model produces a name→pk dict

```python
def _build_m2m_pk_map(
    self, per_model: dict[type[BaseModel], set[tuple]]
) -> dict[type[BaseModel], dict[tuple, int]]:
    """One SELECT per model. Returns ``{model: {key_tuple: pk}}``."""
    pk_map: dict[type[BaseModel], dict[tuple, int]] = {}
    for model, key_tuples in per_model.items():
        rels = FIELD_NAME_KEYS_REL_MAP[model.__name__.lower()]
        # Fall back to "name" for plain NamedModels
        if not rels:
            rels = ("name",)
        # Build a Q-OR over the key tuples (batched if needed for
        # SQLite's variable-count cap)
        filter_q = self._build_m2m_filter_q(rels, key_tuples)
        rows = model.objects.filter(filter_q).values_list(
            "pk", *rels
        )
        pk_map[model] = {row[1:]: row[0] for row in rows}
    return pk_map
```

### Step 3: per-comic loop becomes dict lookups

```python
def link_prepare_m2m_links(self, status):
    link_m2ms = self.metadata.get(LINK_M2MS, {})
    if not link_m2ms:
        return {}

    # Phase A: one pass to collect names per model
    per_model = self._collect_m2m_names_per_model(link_m2ms)

    # Phase B: batched name→pk lookup, one SELECT per model
    pk_map = self._build_m2m_pk_map(per_model)

    # Phase C: per-comic stitch — pure dict lookups, no SQL
    all_m2m_links = {}
    comic_paths = tuple(link_m2ms.keys())
    comics = Comic.objects.filter(path__in=comic_paths).values_list("pk", "path")
    for comic_pk, comic_path in comics:
        md = link_m2ms[comic_path]
        for field_name, value_tuples in md.items():
            model = Comic._meta.get_field(field_name).related_model
            field_pk_map = pk_map.get(model, {})
            pks = tuple(
                field_pk_map[t] for t in value_tuples if t in field_pk_map
            )
            if pks:
                all_m2m_links.setdefault(field_name, {})[comic_pk] = pks
    self.metadata.pop(LINK_M2MS, None)
    return all_m2m_links
```

## Query count

| | per import |
| --- | --- |
| **Before** | `4 × N + ~7 × N + 1` per comic = ~11N + 1 SELECTs (for 600k comics: ~6.6M) |
| **After** | 1 SELECT per M2M model + 1 for the comic.pk/path map = ~12 SELECTs total |

The Python work (collect-names + dict-lookup loop) does N
iterations either way; the win is in eliminating the per-iteration
DB round-trip.

## Memory cost

The `pk_map` holds `dict[(model, key_tuple) → pk]` for every
unique M2M value across the import. For 600k comics:

- Characters: probably 100k-500k unique names
- Tags: maybe 50k-200k unique
- Genres / locations / teams / series_groups / stories: smaller

Conservatively ~1M entries, each `(model, tuple) → int`. Python
dict overhead is ~200 bytes per entry → ~200 MB peak.

Reasonable on any modern import host. But callout in the sub-plan:
if the user's libraries push past this, batch the model lookups
into chunks of 100k unique names.

## Correctness invariants

- **M2M-row identity stays the same.** The map maps existing FK
  rows by their natural keys (name for NamedModel; complex tuple
  for Credit / Identifier / StoryArcNumber). The batched lookup
  produces the same `pk` for the same `(name|tuple)` as the
  per-comic approach.
- **Folders complex-link**: special case. Folders are looked up
  by `path__in` (line 30-33). Same shape as named M2Ms; batches
  cleanly via the same helper with `path` as the key field.
- **Failure modes preserved**: if a name doesn't exist in the DB
  (i.e. wasn't created by `create_and_update` because of an
  earlier failure), the per-comic loop currently produces an
  empty `pks` tuple and skips that field. The batched version
  preserves this — `field_pk_map[t]` raises KeyError, the `if t
  in field_pk_map` guard keeps it. The comic just doesn't link
  to a missing FK row.

## Test plan

- **Unit test**: build a fixture with 100 comics × 10 unique
  characters each. Assert pre-fix and post-fix produce
  identical `all_m2m_links` dicts.
- **Query count regression**: wrap `link_prepare_m2m_links` in
  `CaptureQueriesContext`. Assert ≤ N+5 queries (where N =
  number of distinct M2M models, ~12 today). Fail if a
  refactor reintroduces the per-comic SELECT.
- **Wall clock**: on a 10k-comic dev fixture, expect 5-30×
  speedup on this phase.

## Suggested commit shape

One PR, one commit. The diff touches one file (`link/prepare.py`)
plus possibly a new helper module (`link/lookups.py`) for the
name→pk batching. ~150 LOC added, ~100 LOC removed. Net ~+50.

## Risks

- **Variable count cap on SQLite IN clauses.** A model with 100k
  unique names can't go into a single `name IN (...)` query.
  Batch into chunks of 30000 (matches `IMPORTER_LINK_FK_BATCH_SIZE`).
- **Composite-key models** (Credit, Identifier, StoryArcNumber)
  require multi-column lookups. Use `Q` OR-chain: `Q(
  person_name="X", role_name="Y") | Q(person_name="A",
  role_name="B") | …`. Cap chunk size at the OR-chain limit
  (~900 OR-chained `Q`s before SQLite plans poorly). Fall back
  to a SELECT-then-Python-filter for very wide combinations.
- **None-valued tuple components** (e.g. Identifier has
  nullable `id_url`). Batch SQL filter must handle NULL via
  `Q(field__isnull=True)` rather than `field=None`.
