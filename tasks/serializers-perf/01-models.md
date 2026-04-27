# 01 — Model serializers + metadata pane

This sub-plan absorbs the
`tasks/browser-views-perf/stage5e-handoff-serializer-audit.md`
handoff and extends to the rest of `codex/serializers/models/`.

## Surface

`codex/serializers/models/`:

- `base.py` — `BaseModelSerializer` (abstract, lightweight)
- `comic.py` — `ComicSerializer` (35–85, hot via metadata pane)
- `groups.py` — `Publisher` / `Imprint` / `Series` / `Volume` /
  `GroupModel` serializers (12–55, lightweight)
- `named.py` — 22 classes (30–249, hot — URLNamedModelSerializer
  family)
- `bookmark.py` — `BookmarkSerializer` (lightweight)
- `admin.py` — `LibrarianStatusSerializer` (lightweight)
- `pycountry.py` — `CountrySerializer` / `LanguageSerializer`
  (lightweight; pycountry cost is in `fields/browser.py` —
  see [05-fields.md](./05-fields.md))

`codex/serializers/browser/metadata.py`:

- `MetadataSerializer` — extends `ComicSerializer`, hot via
  `/api/v3/c/<pk>/metadata`.

## Hot endpoint

`/api/v3/c/<pk>/metadata` — `flow_c2_comic_metadata`.

Stage 5d landed at 47 cold queries / 137 ms
(`tasks/browser-views-perf/stage5d-after.json`). Stages 1–4
collapsed the queryset side; the remaining 47 cold queries split
roughly into ~8 per-request setup + ~12 metadata intersection
+ unknown serializer-time evaluation. The audit's job is to
attribute the unknown bucket and either patch what's eliminable or
mark "verified clean".

## Findings

### F1 — Audit serializer-time query count for flow_c2

**Inherited from handoff.** Run silk against
`flow_c2_comic_metadata` cold path; attribute each query to one of:

- per-request setup (~8: session, AdminFlag, library visibility ×4,
  age-rating max, ACL filter)
- `qs[0]` materialization (~1)
- `_query_groups` (depth-dependent, 0–4)
- `_get_comic_pks` distinct values_list (~1)
- `_query_fk_intersections` lazy querysets evaluated by
  `_copy_fks.first()` (~7)
- `_query_m2m_intersections` UNION + hydrations (~12)
- **serializer-time queries (target: 0)**

Anything > 0 in the last bucket is the audit's yield.

**Reproduction**:

```bash
DEBUG=1 SILK_ENABLED=1 \
  uv run pytest tests/perf/run_baseline.py::flow_c2_comic_metadata \
    --with-silk \
    --tb=short
```

Then read the silk JSON output and write the attribution into
`tasks/serializers-perf/investigation-flow-c2.json`.

**Done state**: each of the 47 queries assigned to a bucket. If the
serializer-time bucket is empty, the finding is "verified-clean"
and the rest of this sub-plan covers preventive coverage. If
non-empty, follow up per F2–F5.

### F2 — `URLNamedModelSerializer.url` chain coverage

`codex/serializers/models/named.py:43`:

```python
class URLNamedModelSerializer(NamedModelSerializer):
    url = URLField(read_only=True, source="identifier.url")
```

Subclasses (10): `CreditPersonSerializer`, `CreditRoleSerializer`,
`CharacterSerializer`, `GenreSerializer`, `LocationSerializer`,
`StorySerializer`, `StoryArcSerializer`, `TagSerializer`,
`TeamSerializer`, `UniverseSerializer`.

**Existing coverage** (`codex/views/browser/metadata/const.py`):

```python
M2M_QUERY_OPTIMIZERS  # default select=("identifier",)
                     #  + only=("name", "identifier")
```

The default M2M optimizer picks up `identifier` for one-hop access
across all 10 subclasses. Genre, Location, Story, Tag fall through
to default — confirm with a silk capture that they fire 0 extra
queries during serialization.

**Test:**

```python
# tests/serializers/test_metadata_no_extra_queries.py
def test_url_named_serializers_zero_extra_queries(comic_with_full_md):
    view = MetadataView()
    view.kwargs = {"pk": comic_with_full_md.pk}
    obj = view.get_object()
    serializer = MetadataSerializer(obj)
    with CaptureQueriesContext(connection) as ctx:
        _ = serializer.data
    assert len(ctx.captured_queries) == 0, (
        f"Serializer-time queries: {ctx.captured_queries}"
    )
```

### F3 — `StoryArcNumberSerializer` 2-hop chain

`codex/serializers/models/named.py:164`:

```python
url = URLField(read_only=True, source="story_arc.identifier.url")
```

**Existing coverage**: `M2M_QUERY_OPTIMIZERS[StoryArcNumber]` has
`prefetch=("story_arc", "story_arc__identifier")` — both hops
covered.

Same test as F2 with a comic that has a story arc number.

### F4 — `IdentifierSeralizer.name` property reads `Identifier.source`

`codex/serializers/models/named.py:111-121`:

```python
class IdentifierSeralizer(BaseModelSerializer):
    name = CharField(read_only=True)  # <-- model property reads .source
```

`Identifier.name` is a `@property` on the model that reads
`self.source` (FK to `IdentifierSource`). Serialization triggers
`Identifier.source` access per Identifier.

**Existing coverage**: `M2M_QUERY_OPTIMIZERS[Identifier]` has
`select=("source",)` — covered for the top-level `identifiers`
field. **But** nested Identifiers reached via
`Credit.role__identifier` and `StoryArcNumber.story_arc__identifier`
prefetches also need the `source` prefetched if any of their
attributes are read. Today only `.url` is read for those nested
paths (via `URLNamedModelSerializer`), and `.url` doesn't read
`.source`, so this is **safe in current usage** — but a fragile
invariant.

**Mitigation:** rename the `IdentifierSeralizer` typo (also fixes
the spelling) and document the invariant. Optional defensive fix:
`select_related("source")` on the nested identifier prefetches too.

### F5 — `AgeRatingSerializer.metron` nested FK

`codex/serializers/models/named.py:196`:

```python
class AgeRatingSerializer(NamedModelSerializer):
    metron = AgeRatingMetronSerializer(allow_null=True, read_only=True)
```

Two-hop: `obj.metron.name`, `obj.metron.index`.

**Existing coverage**: `FK_QUERY_OPTIMIZERS[AgeRating]` has
`select=("metron",)` + `only=("name", "metron__name", "metron__index")`.
Covered.

### F6 — `ComicSerializer.Meta.depth = 1`

`codex/serializers/models/comic.py:35`:

```python
class ComicSerializer(BaseModelSerializer):
    ...
    class Meta(BaseModelSerializer.Meta):
        model = Comic
        exclude = ("folders", "parent_folder", "stat")
        depth = 1
```

`depth=1` causes DRF to auto-nest every Comic FK that isn't
explicitly declared or excluded. `parent_folder` is excluded;
all 12 explicitly-declared FKs override `depth=1` for their fields;
`folders` is M2M (excluded). **Effective:** `depth=1` is a no-op.

**Action:** drop it for clarity. The diff is one line and the
behavior is unchanged. Land in the same commit as F1 conclusion.

### F7 — `IdentifierSeralizer` typo

`codex/serializers/models/named.py:111` — `Seralizer` should be
`Serializer`. Cosmetic; rename touches one file plus its imports.
Bundle with another commit.

### F8 — Other model serializers (groups, bookmark, admin,
pycountry)

These are tiny and do not appear in the hot path:

- `groups.py` — 4 serializers each with 2 fields (pk, name).
  No FK chains, no SMFs. **Verified clean.**
- `bookmark.py` — input/output for reader bookmark writes.
  Scalar fields only. **Verified clean.**
- `admin.py:LibrarianStatusSerializer` — exclude-only, no SMFs.
  **Verified clean.**
- `pycountry.py` — uses `CountryField`/`LanguageField` from
  `fields/browser.py`. Cost lives in the field, not the
  serializer. Covered by [05-fields.md](./05-fields.md).

## Suggested commit shape

If F1 audit yields zero serializer-time queries:

1. **F1 + F6 + F7 audit-clean commit.** Add the
   `assertNumQueries`-style test from F2/F3, drop `depth=1`, fix
   the `Seralizer` typo. Document the invariant in F4 as a
   docstring.

If F1 yields > 0 queries:

1. **F1 patch commit** for the offending serializer + a regression
   test that pins the new query count.
2. **F6 + F7 cleanup commit** (independent of the patch).

## Verification

- `make test-python` clean (existing tests).
- New `tests/serializers/test_metadata_no_extra_queries.py` passes
  with the Comic-fixture-richest-M2M-coverage helper from
  `tests/perf/run_baseline.py`.
- Silk attribution for `flow_c2_comic_metadata`: serializer-time
  bucket is 0.
- `tasks/browser-views-perf/stage5e-handoff-serializer-audit.md`
  updated with a final paragraph linking to this plan + the
  conclusion ("verified clean" or "patched in PR #N").

## References

- `tasks/browser-views-perf/stage5e-handoff-serializer-audit.md` —
  source handoff doc with detailed reproduction steps.
- `tasks/browser-views-perf/04-metadata.md` #9 — the original entry
  that flagged this risk.
- `tasks/browser-views-perf/05-replan.md` §10 — Stage 5d landing
  notes (47 cold queries baseline).
