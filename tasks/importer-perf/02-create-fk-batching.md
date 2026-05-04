# 02 — Create / update FK row batching

Per-row FK SELECTs hidden in the create and update paths. Lower
absolute count than [01-link-batching](./01-link-batching.md), but
still significant for libraries with thousands of unique
publishers / imprints / series.

## Hot path

`create/foreign_keys.py:46-75` — `_get_create_update_args`:

```python
@staticmethod
def _get_create_update_args(
    model: type[BaseModel],
    key_args_map: Mapping,
    update_args_map: Mapping,
    values_tuple: tuple,
) -> tuple[dict, dict]:
    key_args = {}
    update_args = {}
    num_keys = len(key_args_map)
    for index, (field_name, field_model) in enumerate(
        chain(key_args_map.items(), update_args_map.items())
    ):
        value = values_tuple[index]
        if field_model and value is not None:
            ...
            sub_model_key_args = dict(zip(key_rels, value, strict=True))
            value = field_model.objects.get(**sub_model_key_args)  # ← N+1
        ...
```

For every row being created, every nested FK reference fires a
fresh `model.objects.get(...)`. Examples:

- **Imprint creation** dereferences `publisher`. 1 publisher
  SELECT per imprint.
- **Series creation** dereferences `publisher` and `imprint`. 2
  SELECTs per series.
- **Volume creation** dereferences `publisher`, `imprint`,
  `series`. 3 SELECTs per volume.
- **Identifier creation** dereferences `source`. 1 SELECT per
  identifier.

For a fresh import with 600k comics:

| Model being created | Approx unique rows | FK SELECTs each | Total |
| ------------------- | ------------------ | --------------- | ----- |
| Imprint | ~5,000 | 1 | 5k |
| Series | ~30,000 | 2 | 60k |
| Volume | ~150,000 | 3 | 450k |
| StoryArcNumber | ~50,000 | 1 | 50k |
| Credit | ~500,000 | 2 | 1M |
| Identifier | ~600,000 | 1 | 600k |

Conservatively **~2 million SELECTs** in this phase across a
fresh 600k-comic import.

## Same shape in the update path

`create/foreign_keys.py:189` — `_bulk_update_models`:

```python
for values_tuple in update_tuples:
    key_args, update_args = self._get_create_update_args(...)
    obj = model.objects.get(**key_args)  # ← N+1
    for key, value in update_args.items():
        setattr(obj, key, value)
```

Plus the same `_get_create_update_args` runs inside, so the
inner FK dereferences are also N+1.

For repeat imports where most FKs already exist, the update
path runs more often than create.

## Why this happens

`_get_create_update_args` translates flat tuples like
`(publisher_name, imprint_name, name, ...)` into Django ORM
`(publisher=Publisher_instance, imprint=Imprint_instance,
name="...")`. The `field_model.objects.get(**sub_model_key_args)`
fetches a fresh model instance because Django's `bulk_create`
expects FK fields to be set as model instances, not bare pks.

But `bulk_create` actually accepts `<field>_id=<pk_int>` directly
— skipping the instance round-trip. The SELECT exists only to
satisfy the ORM's typing.

## Fix sketch

Pre-fetch parent FKs ONCE per model, before the create/update
loop. Pass the pk directly via `<field>_id=` in the create kwargs.

```python
def _build_parent_fk_pk_maps(
    self, model: type[BaseModel],
) -> dict[type[BaseModel], dict[tuple, int]]:
    """Pre-fetch every parent FK referenced by ``model``'s create rows.

    Returns ``{parent_model: {key_tuple: pk}}``. The create loop
    looks up parent pks here instead of firing
    ``parent_model.objects.get(...)`` per row.
    """
    pk_maps = {}
    key_args_map, update_args_map = MODEL_CREATE_ARGS_MAP[model]
    for field_name, field_model in chain(
        key_args_map.items(), update_args_map.items()
    ):
        if not field_model or field_model in pk_maps:
            continue
        rels = MODEL_REL_MAP[field_model][0]
        rows = field_model.objects.values_list("pk", *rels)
        pk_maps[field_model] = {row[1:]: row[0] for row in rows}
    return pk_maps

def _get_create_update_args(
    self,
    model: type[BaseModel],
    key_args_map: Mapping,
    update_args_map: Mapping,
    values_tuple: tuple,
    pk_maps: dict,  # ← passed in once per model batch
) -> tuple[dict, dict]:
    ...
    if field_model and value is not None:
        ...
        # Was: field_model.objects.get(**sub_model_key_args)
        # Now: dict lookup, no SQL
        pk = pk_maps[field_model].get(tuple(value))
        # Pass pk via the ``_id`` shortcut to bypass FK descriptor
        arg_map = key_args if index < num_keys else update_args
        arg_map[field_name + "_id"] = pk
        continue
    ...
```

The `<field>_id=<pk>` form is well-supported by Django and
`bulk_create` since ~1.4. No FK instance is ever materialized.

## Query count

For a fresh 600k-comic import:

| | per phase |
| --- | --- |
| **Before** | ~2M SELECTs across all FK creates |
| **After** | 1 SELECT per parent FK model = ~10 SELECTs total |

Plus the existing bulk_create / bulk_update SQL stays the same.

## Memory cost

The pk_maps for parent FK lookup hold up to ~150k Volume entries
(rare worst case, since Volumes are created mostly during this
same phase — early-phase Imprint creation only sees the Publisher
map, which is much smaller).

Worst case ~500MB peak for an import with millions of unique
parent rows. Worth flagging; can chunk per-model lookup if a
threshold is hit.

## Correctness invariants

- **FK row identity preserved**: the pk_map keys off the same
  `MODEL_REL_MAP[field_model][0]` tuple the per-row code uses, so
  the same pk is selected.
- **`presave()` still runs**: the existing loop calls
  `obj.presave()` after the kwargs are assembled. That stays —
  presave doesn't depend on FK instance materialization.
- **`<field>_id` vs `<field>` semantics**: passing
  `publisher_id=42` is equivalent to `publisher=Publisher(pk=42)`
  for `bulk_create` purposes — same column written. No descriptor
  difference at the DB row level.
- **NULL FKs**: `pk_maps[field_model].get(tuple(value))` returns
  `None` when the value is missing. Pass `field_id=None` (since
  `null=True` on those FKs). Same shape as the previous code's
  None-handling (line 71-72).

## Risks

- **`MODEL_CREATE_ARGS_MAP` and `MODEL_REL_MAP` typing.** The
  current code relies on Django's FK-descriptor unboxing. Going
  to `_id=int` requires the consts be aware of which fields are
  FKs vs scalar. Verify by reading `const.py` and asserting
  `field_name + "_id"` is a real DB column on the target model.
- **Bulk_create with `update_conflicts=True`**: Django's
  conflict-target update relies on `update_fields` matching real
  column names. If `update_fields` is currently set to
  `("publisher", ...)` (the FK descriptor name), it might need to
  become `("publisher_id", ...)` after the change. Verify in
  isolation.
- **Test fixture**: build a small fixture covering each create
  path (Publisher → Imprint → Series → Volume → Comic). Assert
  pk_map approach produces the same DB rows as the per-row
  approach.

## Suggested commit shape

One PR. Touches `create/foreign_keys.py` and possibly
`create/const.py`. ~100 LOC change.

Bundles cleanly with [01-link-batching.md](./01-link-batching.md)
since both are pure batching refactors with no schema implications,
but ship as separate PRs to keep blast radius small.

## Test plan

- **Round-trip test**: create N=1000 comics with 200 unique
  publishers/imprints/series. Run import twice (once with the
  old code, once with new). Assert every Comic, Publisher,
  Imprint, Series, Volume row's `(pk, key_columns)` tuple is
  identical.
- **Query count regression**: assert
  `_bulk_create_models(Volume, status)` fires no more than
  K + 2 SELECTs (K = number of parent FK models pre-fetched
  once).
- **Wall clock**: on a 10k-comic dev fixture, expect 2-5×
  speedup on the create_and_update phase.
