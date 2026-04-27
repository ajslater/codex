# Stage 5e — Handoff: ComicSerializer N+1 audit

> **Status (April 2026):** absorbed into
> [`tasks/serializers-perf/01-models.md`](../serializers-perf/01-models.md)
> as Finding F1 (audit serializer-time query count for flow_c2). The
> per-finding scoping below (Gap 1–5) is preserved verbatim but the
> implementation steps live in the linked sub-plan.

This is a handoff doc, not the audit itself. The Stage 5e investigation has been
moved into a future Claude session that will pair it with other serializer-layer
perf work. This doc captures the scouting already done so the next session can
land running.

The deliverable named in `05-replan.md` §4 was
`tasks/browser-views-perf/investigation-serializer.md` — that file does not
exist yet, and this handoff is the input it should be written from.

## Why this matters

`flow_c2_comic_metadata` (`/api/v3/c/<pk>/metadata`) currently runs at **47 cold
queries / 137 ms** (`stage5d-after.json`). Stages 1–4 already batched the
visible offenders: M2M union hydration, FK intersection batching, group queries,
value-field annotations. The 47 remaining cold queries include per-request setup
(~8 queries), the intersection pipeline, and any **lazy FK access fired during
DRF serialization itself**. The audit's job is to confirm which of those 47 are
serializer-time and whether any are eliminable.

`04-metadata.md` #9 is the entry that flagged this risk; this handoff is the
scouting done to hand off that entry.

## Scope confirmation

`ComicSerializer` is consumed by **exactly one** caller:

```
$ grep -rn "ComicSerializer" codex/
codex/serializers/models/comic.py:35:class ComicSerializer(BaseModelSerializer):
codex/serializers/browser/metadata.py:7:from ...
codex/serializers/browser/metadata.py:26:class MetadataSerializer(...)
codex/serializers/browser/metadata.py:71:class Meta(ComicSerializer.Meta):
codex/serializers/browser/metadata.py:75:        *ComicSerializer.Meta.exclude,
```

So the audit can stay focused on `MetadataSerializer` and its
`MetadataView.get_object()` feed. `ReaderComicSerializer` is a plain
`Serializer` with scalar fields only (`codex/serializers/reader.py:54-90`); it
does not extend `ModelSerializer` and has no FK-access risk.
`BrowserCardSerializer`'s cover `SerializerMethodField`s use
`getattr(..., None)` fallback to `obj.pk` — safe.

## ComicSerializer landscape

`codex/serializers/models/comic.py:35-85`:

- `Meta.model = Comic`, `Meta.exclude = ("folders", "parent_folder", "stat")`,
  `Meta.depth = 1`. The `depth=1` alone causes DRF to auto-nest every FK on
  Comic that isn't excluded.
- 12 explicit nested-FK serializers (override the `depth=1` defaults):
    - **Group FKs** (4): `publisher`, `imprint`, `series`, `volume` — but
      `MetadataSerializer.Meta.exclude` strips these and replaces with `*_list`
      GroupSerializer instances populated from
      `MetadataCopyIntersectionsView._copy_groups`. **Not a serializer-time
      risk** in the metadata path.
    - **pycountry FKs** (2): `country`, `language` — `CountrySerializer` /
      `LanguageSerializer` resolve at the Python level via pycountry; they
      **don't hit the database** (`codex/serializers/models/pycountry.py`).
    - **Other FKs** (6): `age_rating`, `original_format`, `scan_info`, `tagger`,
      `main_character`, `main_team`. These hit the DB if the FK target row isn't
      already loaded.
- 11 explicit M2M serializers: `characters`, `credits`, `genres`, `identifiers`,
  `locations`, `series_groups`, `stories`, `story_arc_numbers`, `tags`, `teams`,
  `universes`. In `MetadataSerializer`, `credits`, `identifiers`, and
  `story_arc_numbers` rebind to `attached_*` (PREFETCH_PREFIX) — populated by
  `MetadataCopyIntersectionsView._copy_m2m_intersections`.

## Risk hotspots from URL/property fields

These are the access patterns that will fire extra queries during serialization
unless the upstream queryset hydrates them:

1. **`URLNamedModelSerializer.url`** `codex/serializers/models/named.py:43`:

    ```python
    url = URLField(read_only=True, source="identifier.url")
    ```

    One-hop FK access (`obj.identifier.url`). Subclasses:
    `CreditPersonSerializer`, `CreditRoleSerializer`, `CharacterSerializer`,
    `GenreSerializer`, `LocationSerializer`, `StorySerializer`,
    `StoryArcSerializer`, `TagSerializer`, `TeamSerializer`,
    `UniverseSerializer` (10 classes).

2. **`StoryArcNumberSerializer.url`** `codex/serializers/models/named.py:164`:

    ```python
    url = URLField(read_only=True, source="story_arc.identifier.url")
    ```

    **Two-hop FK access** (`obj.story_arc.identifier.url`) — needs
    `select_related("story_arc__identifier")`.

3. **`IdentifierSeralizer.name`** `codex/serializers/models/named.py:111-121`
   declares `name = CharField(read_only=True)`. `Identifier.name` is a
   `@property` that reads `self.source` (FK) — every serialized Identifier
   triggers `Identifier.source` access.

4. **`AgeRatingSerializer.metron`** `codex/serializers/models/named.py:196`:
    ```python
    metron = AgeRatingMetronSerializer(allow_null=True, read_only=True)
    ```
    Nested FK from AgeRating → AgeRatingMetron. Needs `select_related("metron")`
    on the AgeRating queryset.

## Existing optimizer coverage

`codex/views/browser/metadata/const.py:61-111` defines two MappingProxyType
dispatch tables that `query_intersections.py` consults when building each
intersection queryset:

`FK_QUERY_OPTIMIZERS` (3 entries):

| Model     | select       | only                                    |
| --------- | ------------ | --------------------------------------- |
| AgeRating | `metron`     | `name`, `metron__name`, `metron__index` |
| Character | `identifier` | `name`, `identifier__url`               |
| Team      | `identifier` | `name`, `identifier__url`               |

`M2M_QUERY_OPTIMIZERS` (6 entries):

| Model          | prefetch                                                   | select    | only                                |
| -------------- | ---------------------------------------------------------- | --------- | ----------------------------------- |
| Credit         | `role`, `person`, `role__identifier`, `person__identifier` | —         | `role`, `person`                    |
| StoryArcNumber | `story_arc`, `story_arc__identifier`                       | —         | `story_arc`, `number`               |
| Identifier     | —                                                          | `source`  | `source`, `key`, `url`              |
| Universe       | —                                                          | (default) | `name`, `designation`, `identifier` |
| SeriesGroup    | —                                                          | (none)    | `name`                              |
| Folder         | —                                                          | (none)    | `path`                              |

Defaults (`query_intersections.py:_get_optimized_fk_query` and
`_get_optimized_m2m_query`):

- FK default: `only=("name",)`. **No `select_related` by default** — so the six
  "Other FKs" on Comic that aren't in the table get nothing.
- M2M default: `select=("identifier",)`, `only=("name", "identifier")`. This is
  exactly what `URLNamedModelSerializer` needs (one-hop `identifier.url`).

## Coverage gaps the audit should verify

These are the open questions that determine whether the audit produces a patch
or just a "no-op confirmed clean" doc:

### Gap 1 — M2M defaults already cover URLNamedModelSerializer subclasses

`Genre`, `Location`, `Story`, `Tag` are URLNamedModelSerializer subclasses
**not** in `M2M_QUERY_OPTIMIZERS`. They fall through to the default
`select=("identifier",)` + `only=("name", "identifier")`. That happens to be
correct for `url = URLField(source="identifier.url")` — confirm there's no
hidden cost (e.g. `Identifier.source` property access, since
`IdentifierSeralizer` is not in the M2M Identifier serializer chain for these
models — `URLNamedModelSerializer.url` only reads `identifier.url` directly, not
the Identifier's name).

**Test:** capture queries during serialization of one comic that has
genres/locations/stories/tags. Expected: 0 extra queries beyond the intersection
hydration itself.

### Gap 2 — FK_QUERY_OPTIMIZERS gaps for "Other FKs"

The six Other FKs (`age_rating`, `original_format`, `scan_info`, `tagger`,
`main_character`, `main_team`) are hydrated through `_query_fk_intersections` →
`_copy_fks` (`fk_qs.first()`). `FK_QUERY_OPTIMIZERS` covers AgeRating, Character
(= main_character path), Team (= main_team path). Missing: `OriginalFormat`,
`ScanInfo`, `Tagger`.

These three are simple `NamedModelSerializer` subclasses (just `pk`, `name`) —
the default `only=("name",)` is correct. **Likely no work needed**, but worth a
1-comic silk capture to confirm.

### Gap 3 — Main queryset materialization on `model is Comic`

`MetadataView.get_object()` (`codex/views/browser/metadata/__init__.py:71-106`)
runs `qs[0]` on the annotated Comic queryset, then `_copy_fks` overwrites each
FK attribute with an optimized intersection-fk queryset's `.first()`.

**Question:** does `qs[0]` itself fire any additional queries due to attribute
access on the resulting Comic instance during the rest of `get_object()`? In
particular, the chain is:

```
qs[0] -> _aggregate_multi_pk_sums (only when len(pks) > 1)
      -> query_intersections (drives 7 fk + 11 m2m queries)
      -> copy_intersections_into_comic_fields
          -> _path_security (reads obj.path)
          -> _highlight_current_group (model-name based)
          -> _copy_groups (sets *_list)
          -> _copy_fks (fk_qs.first() per FK — 7 queries)
          -> _copy_m2m_intersections (sets attached_* / m2m fields)
```

`_path_security` calls `obj.search_path()` only when admin_flag set; otherwise
reads `obj.path` (already in `qs[0]`). No serializer-time risk here.

The hand-off audit should still verify by running silk on flow_c2 and
attributing each of the 47 cold queries to a stage.

### Gap 4 — `Identifier.name` property on `IdentifierSeralizer`

`Identifier.name` is a `@property` that reads `self.source` (FK to
`IdentifierSource`). The `M2M_QUERY_OPTIMIZERS[Identifier]` entry includes
`select=("source",)` — so the FK is loaded eagerly when the M2M intersection
queryset is hydrated. **Looks safe**, but the audit should confirm the
identifier prefetches on `Credit.role__identifier` and
`StoryArcNumber.story_arc__identifier` paths similarly load `identifier.source`
if `name` is read for those nested Identifiers (in this codebase,
`IdentifierSeralizer` is only mounted on the top-level `identifiers` field of
MetadataSerializer, so probably not a cross-cutting issue).

### Gap 5 — `Meta.depth = 1` on ComicSerializer

`depth=1` causes DRF to **auto-nest every Comic FK that isn't explicitly
serialized or excluded**. The exclude list is
`("folders", "parent_folder", "stat")` — but folders is M2M and parent_folder is
the only "extra" FK. All other Comic FKs are explicitly serialized, which
**overrides depth=1** for that field. Effective: depth=1 changes nothing — it's
belt-and-braces. The audit could note this (and possibly drop `depth=1` for
clarity), but it's not a perf win.

## MetadataView.get_object() flow (reference map)

```
codex/views/browser/metadata/__init__.py:72-106
  filter -> annotate_order/card/cover/values_and_fks/group_by/inner_joins
  qs[0]  ->  obj
  query_intersections(filtered_qs)
    -> _query_groups()                    [N queries, N = group depth]
    -> _get_comic_pks(filtered_qs)        [1 query, distinct values_list]
    -> _query_fk_intersections(comic_pks) [7 lazy querysets,
                                           hydrated by _copy_fks below]
    -> _query_m2m_intersections(comic_pks)[1 UNION + 11 hydration querysets]
  copy_intersections_into_comic_fields(obj, ...)
    -> _copy_fks: fk_qs.first() x 7 fields
    -> _copy_m2m_intersections: setattr or .set(qs, clear=True)
serializer.data
  -> walks ComicSerializer fields, then MetadataSerializer fields
  -> THIS IS WHERE ANY MISSED select_related FIRES EXTRA QUERIES
```

## Files to read (with the relevant line ranges)

Serializers:

- `codex/serializers/models/comic.py:35-85` — `ComicSerializer`
- `codex/serializers/browser/metadata.py:14-81` — `MetadataSerializer`
- `codex/serializers/models/named.py:30-249` — full `URLNamedModelSerializer`
  family + `IdentifierSeralizer` + `StoryArcNumberSerializer` +
  `AgeRatingSerializer`
- `codex/serializers/browser/mixins.py:21-71` —
  `BrowserAggregateSerializerMixin` (`get_mtime` reads only annotations; safe)
- `codex/serializers/models/groups.py` — group serializers (pk + name; safe)
- `codex/serializers/models/pycountry.py` — Country/Language (Python-side
  resolution; safe)
- `codex/serializers/reader.py:54-90` — `ReaderComicSerializer` (plain
  Serializer, scalar fields only; safe)

Views:

- `codex/views/browser/metadata/__init__.py:21-119` — `MetadataView`
  (`get_object` flow)
- `codex/views/browser/metadata/const.py:61-111` — `FK_QUERY_OPTIMIZERS` +
  `M2M_QUERY_OPTIMIZERS`
- `codex/views/browser/metadata/query_intersections.py:55-160` —
  `_get_optimized_fk_query`, `_get_optimized_m2m_query`,
  `_query_fk_intersections`, `_query_m2m_intersections`
- `codex/views/browser/metadata/copy_intersections.py` — `_copy_fks`,
  `_copy_m2m_intersections`

Models (for property-access risk):

- `codex/models/identifier.py` — `Identifier.name` is a `@property` reading
  `self.source`

Background:

- `tasks/browser-views-perf/04-metadata.md:219-232` — original #9 entry
- `tasks/browser-views-perf/04-metadata.md:273-292` — Stage-1 query-count
  baseline
- `tasks/browser-views-perf/05-replan.md` §10 — Stage 5d landing notes

## Suggested verification approach

1. **Silk capture on `flow_c2_comic_metadata` cold path.** The harness in
   `tests/perf/run_baseline.py` already wires silk via the `--with-silk` flag.
   Run with silk enabled and attribute each of the 47 cold queries to a stage:
    - per-request setup (~8: session, AdminFlag, library visibility ×4,
      age-rating max, ACL filter)
    - `qs[0]` materialization (~1)
    - `_query_groups` (depth-dependent, 0-4)
    - `_get_comic_pks` distinct values_list (~1)
    - `_query_fk_intersections` lazy querysets evaluated by `_copy_fks.first()`
      (~7)
    - `_query_m2m_intersections` UNION + hydrations (~12)
    - serializer-time queries (target: 0; **anything > 0 here is the audit's
      yield**)

2. **Per-field `connection.queries` diff.** For each of the 11 M2M fields and 6
   Other FKs, wrap `serializer.data` in a `CaptureQueriesContext` and isolate
   the per-field cost.

3. **Confirm Gap 1 by toggling defaults.** Temporarily change
   `_get_optimized_m2m_query`'s default `select=("identifier",)` to `()` —
   verify the genres/locations/stories/tags fields fire one extra query per row.
   Restore default and confirm zero. This validates the existing default is
   doing real work and shouldn't be loosened.

4. **No-op confirmation is a valid outcome.** If silk shows zero serializer-time
   queries, the audit's deliverable is the `investigation-serializer.md` doc
   with that conclusion + the test methodology, so a future regression can be
   caught.

## Already audited and clean (do not re-audit)

- `BrowserCardSerializer` cover `SerializerMethodField`s — `getattr(..., None)`
  fallback to `obj.pk`.
- `BrowserAggregateSerializerMixin.get_mtime` — reads `obj.updated_ats` /
  `obj.bookmark_updated_ats` annotations (lists of strings).
- `ReaderComicSerializer` — plain `Serializer`, scalar fields only.
- Group `*_list` GroupSerializer in MetadataSerializer — populated from
  `_query_groups` materialized querysets, `name` + `ids` only.
- Country/Language via pycountry — Python-level resolution, no DB.

## Out of scope for the audit

- The 8-query per-request setup (session + ACL pipeline). Scoped out of Stage 5b
  in `05-replan.md` §8 ("Why 5.4 didn't ship").
- Cross-request caching of metadata responses. `cache_page` already applies;
  in-app caching was deferred in `04-metadata.md` §D.
- M2M UNION + hydration query architecture. Already optimized in Stages 1–4.

## Done state

The audit is "done" when `tasks/browser-views-perf/investigation-serializer.md`
exists and contains:

1. A silk-attributed breakdown of `flow_c2_comic_metadata`'s 47 cold queries.
2. For each gap above (Gap 1–5), either "confirmed clean" with the reproduction
   command, or a patch landed in the same PR.
3. An updated `99-summary.md` row for R3 with status set to either
   `verified-clean` or `landed`.
