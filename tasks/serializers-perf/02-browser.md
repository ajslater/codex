# 02 — Browser serializers

This sub-plan covers everything under
`codex/serializers/browser/` except `metadata.py` (in
[01-models.md](./01-models.md)) and the field-level concerns (in
[05-fields.md](./05-fields.md)).

## Surface

- `browser/page.py` — `BrowserCardSerializer`,
  `BrowserPageSerializer` (browser-list response wrapper)
- `browser/choices.py` — filter-menu serializers
- `browser/mixins.py` — `BrowserAggregateSerializerMixin` (mtime,
  ids, child_count, page, finished, progress)
- `browser/settings.py` — settings input/output
- `browser/filters.py` — settings filter input
- `browser/mtime.py` — `/mtime` endpoint
- `browser/saved.py` — saved-settings list

## Hot endpoints

1. `/api/v3/<group>/<pks>/<page>` — browser list. Returns
   `BrowserPageSerializer` with `groups` + `books` arrays of
   `BrowserCardSerializer`. **20–100 cards per response**, fired
   on every page navigation.

2. `/api/v3/<group>/<pks>/choices/<field>` — filter menu pull.
   Returns `BrowserChoicesFilterSerializer` with one `choices`
   array. Fired when the user opens a filter menu (~50 entries
   typical).

## Findings

### F1 — `get_mtime` Python-side datetime parsing **(medium)**

`codex/serializers/browser/mixins.py:38-71`.

```python
@staticmethod
def _get_max_updated_at(mtime, updated_ats) -> datetime:
    for dt_str in updated_ats:
        if not dt_str:
            continue
        try:
            dt = datetime.strptime(
                dt_str, "%Y-%m-%d %H:%M:%S.%f"
            ).replace(tzinfo=UTC)
        except ValueError:
            ...
        mtime = max(dt, mtime)
    return mtime

def get_mtime(self, obj) -> int:
    bmua_is_max = bool(getattr(self.context.get("view"), "bmua_is_max", False))
    updated_ats = (
        obj.updated_ats
        if bmua_is_max
        else chain(obj.updated_ats, obj.bookmark_updated_ats)
    )
    mtime = self._get_max_updated_at(EPOCH_START, updated_ats)
    ...
```

`obj.updated_ats` is a SQLite `GROUP_CONCAT`-style aggregate of
timestamp strings. Each card calls `_get_max_updated_at`, which
iterates the list and runs `datetime.strptime` per entry.

Per browser-list response: **N cards × ~50 entries × strptime ≈
1000–5000 strptime calls**. `strptime` is the slow datetime parser
in CPython; `datetime.fromisoformat` is ~10× faster on parseable
formats and Python 3.11+ accepts the trailing microseconds.

**Fix A (quick win):** swap to `fromisoformat`:

```python
@staticmethod
def _get_max_updated_at(mtime, updated_ats) -> datetime:
    for dt_str in updated_ats:
        if not dt_str:
            continue
        try:
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=UTC)
        except ValueError:
            logger.warning(...)
            continue
        mtime = max(dt, mtime)
    return mtime
```

Caveat: SQLite's `GROUP_CONCAT` produces space-separated strings
like `2024-01-15 10:30:45.123456`. `fromisoformat` handles the
space separator since Python 3.11. Verify with the dev DB output
shape before flipping.

**Fix B (deeper):** push the max into SQL. The "ORM won't aggregate
aggregates" comment in the existing code points at the underlying
issue: per-row `MAX(updated_at)` is built with `Max("updated_at")`
inside the GROUP BY, but cross-grouping aggregation isn't trivial
in Django's ORM. A custom `Aggregate` subclass could emit
`json_group_array(updated_at)` → `max(...)` directly, but the
diff's larger and risks correctness on the bookmark vs comic
mtime split. **Defer to a follow-up** unless Fix A is insufficient.

**Expected impact:** 5–15 ms saved per browser-list response on
medium-size cards (50 cards × ~50 timestamps each).

### F2 — `BrowserChoicesFilterSerializer.get_choices` per-request
serializer instantiation **(medium)**

`codex/serializers/browser/choices.py:143-160`.

```python
class BrowserChoicesFilterSerializer(Serializer):
    choices = SerializerMethodField(read_only=True)

    def get_choices(self, obj) -> list:
        field_name = obj.get("field_name", "")
        choices = obj.get("choices", [])
        serializer_class = _CHOICES_NAME_SERIALIZER_MAP.get(field_name)
        if serializer_class:
            value = serializer_class(choices, many=True).data
        elif not serializer_class and field_name in _LIST_FIELDS:
            field = (
                BrowserSettingsFilterSerializer()  # <-- per-request instantiation
                .get_fields()
                .get(field_name)
            )
            value = field.to_representation(choices)
        else:
            value = BrowserChoicesIntegerPkSerializer(choices, many=True).data
        return value
```

Two issues:

1. **`BrowserSettingsFilterSerializer().get_fields()`** runs DRF's
   metaclass walk per request. The fields dict is static — can be
   built once at module load.

2. **`field.to_representation(choices)`** uses `field` instances
   bound to a fresh serializer that's about to be discarded — fine
   functionally, but adds GC pressure on the menu pull path.

**Fix:**

```python
# At module load
_LIST_FIELD_REPRESENTATIONS = MappingProxyType({
    name: BrowserSettingsFilterSerializer().get_fields()[name]
    for name in _LIST_FIELDS
})

class BrowserChoicesFilterSerializer(Serializer):
    choices = SerializerMethodField(read_only=True)

    def get_choices(self, obj) -> list:
        field_name = obj.get("field_name", "")
        choices = obj.get("choices", [])
        if serializer_class := _CHOICES_NAME_SERIALIZER_MAP.get(field_name):
            return serializer_class(choices, many=True).data
        if field := _LIST_FIELD_REPRESENTATIONS.get(field_name):
            return field.to_representation(choices)
        return BrowserChoicesIntegerPkSerializer(choices, many=True).data
```

**Expected impact:** modest — the filter-menu pull is a low-volume
endpoint compared to browse-list, but the win is essentially free.

### F3 — `BrowserCardSerializer` cover SMFs **(verified clean)**

`codex/serializers/browser/page.py:20-56`.

```python
cover_pk = SerializerMethodField(read_only=True)
cover_custom_pk = SerializerMethodField(read_only=True)

def get_cover_pk(self, obj):
    return getattr(obj, "cover_pk", None) or obj.pk

def get_cover_custom_pk(self, obj):
    return getattr(obj, "cover_custom_pk", None) or 0
```

Already audited in the handoff doc. Falls back to `obj.pk` when
the annotation is missing — safe and cheap. No fix.

### F4 — `BrowserPageSerializer` nested `many=True` **(verified
clean)**

`codex/serializers/browser/page.py:74-89`.

Just two `BrowserCardSerializer(many=True)` arrays for groups +
books. No SMFs of its own. The cost is the per-card cost from F1
+ F3, not the wrapper.

### F5 — `BrowserSettingsSerializer`, `BrowserCoverInputSerializer`
**(verified clean)**

`codex/serializers/browser/settings.py`. Input/output for
`/browser/settings`. Scalar fields, no DB, no SMFs. Hit once per
session.

### F6 — `BrowserSettingsFilterInputSerializer` **(verified clean)**

`codex/serializers/browser/filters.py`. Input validation for the
filter API. Scalar fields, no DB.

### F7 — `MtimeSerializer` / `GroupsMtimeSerializer` **(verified
clean)**

`codex/serializers/browser/mtime.py`. One annotation field; one
input dict. No issues.

### F8 — `SavedBrowserSettingsListSerializer` **(verified clean)**

`codex/serializers/browser/saved.py`. Returns a list of
`SavedSettingNameSerializer`. Already-loaded queryset; no chain.

## Tests to add

`tests/serializers/test_browser_no_extra_queries.py`:

```python
def test_browser_card_zero_extra_queries(populated_browser_qs):
    """Ensure BrowserCardSerializer fires no DB queries."""
    serializer = BrowserPageSerializer({"groups": ..., "books": ...})
    with CaptureQueriesContext(connection) as ctx:
        _ = serializer.data
    assert len(ctx.captured_queries) == 0


def test_get_mtime_handles_aggregate_format():
    """Lock in the parser format for GROUP_CONCAT'd timestamps."""
    obj = SimpleNamespace(
        updated_ats=["2024-01-15 10:30:45.123456",
                     "2024-02-20 11:45:30.000001"],
        bookmark_updated_ats=[],
    )
    serializer = BrowserCardSerializer(context={"view": ...})
    mtime = serializer.get_mtime(obj)
    assert mtime > 0
```

The first test prevents a future regression introducing a hidden
FK access in `BrowserCardSerializer`. The second pins the
`fromisoformat` swap from F1.

## Suggested commit shape

One PR, two commits:

1. **F1**: `_get_max_updated_at` → `fromisoformat`. Add the
   format-parser test to lock in the format. Capture before/after
   wall time on `flow_a_browse_root` (50-card response).
2. **F2**: `_LIST_FIELD_REPRESENTATIONS` module-level cache.
   Microbench: 50× `get_choices` calls before/after with a hot
   field name and a list-field name.

## Verification

- `tests/perf/run_baseline.py` flow_a_browse_root:
  - cold query count unchanged
  - cold + warm wall time: F1 saves measurable Python time
- `tests/perf/run_baseline.py` flow_e_search_plus_covers:
  - same assertion shape
- New unit tests pass.
