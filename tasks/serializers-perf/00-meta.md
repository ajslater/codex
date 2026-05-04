# Serializers performance — meta plan

The serializer layer (`codex/serializers/`) is too large for one
plan file. This document is the table of contents + methodology +
cross-cutting analysis. Per-surface sub-plans land alongside it.

## Why this matters

Codex serializers are on the response hot path of every API
endpoint. Stages 1–5 of the browser-views-perf project trimmed the
queryset side; the serializer side is the next likely lever. Unlike
queryset perf, serializer perf is mostly **per-object work that
multiplies by the cardinality of the response** — N rows × M fields
× hidden lazy attribute access. The wins are smaller than queryset
fixes individually but compound across endpoints.

A single previous handoff doc
(`tasks/browser-views-perf/stage5e-handoff-serializer-audit.md`)
already scoped one serializer (`ComicSerializer` /
`MetadataSerializer`). This project absorbs it as
[04-models.md](./04-models.md) and extends across the rest of the
serializer surface.

## Scope

50+ serializer/field files, ~3,500 LOC, organized as:

```
codex/serializers/
├── __init__.py
├── auth.py                    Dead code (audit confirms — see 04)
├── homepage.py                Single endpoint, scalar fields
├── mixins.py                  General-purpose helpers
├── reader.py                  Reader open response (148 LOC)
├── redirect.py                404 handler shapes
├── route.py                   Frontend route serialization
├── settings.py                Browser settings input
├── versions.py                /versions endpoint
├── admin/
│   ├── flags.py               Admin flag CRUD
│   ├── groups.py              Admin group CRUD (FK source chain)
│   ├── libraries.py           Admin library CRUD (validate_path)
│   ├── stats.py               /admin/stats response (127 LOC)
│   ├── tasks.py               Admin task input
│   └── users.py               Admin user CRUD (FK source chain)
├── browser/
│   ├── choices.py             Filter choice menus (160 LOC)
│   ├── filters.py             Filter input validation
│   ├── metadata.py            Metadata pane (covered by 01)
│   ├── mixins.py              BrowserAggregateSerializerMixin (mtime)
│   ├── mtime.py               /mtime endpoint
│   ├── page.py                BrowserCardSerializer (browser cards)
│   └── settings.py            Browser settings input/output
├── fields/
│   ├── auth.py                TimezoneField, TimestampField
│   ├── base.py                CodexChoiceField
│   ├── browser.py             PyCountryField (hot)
│   ├── group.py               BrowseGroupField
│   ├── reader.py              FitToField, ReadingDirectionField
│   ├── sanitized.py           SanitizedCharField (write-path nh3)
│   ├── settings.py            SettingsKeyField
│   ├── stats.py               StringListMultipleChoiceField,
│   │                          SerializerChoicesField, CountDictField
│   └── vuetify.py             Vuetify form-field adapters
├── models/
│   ├── admin.py               LibrarianStatusSerializer
│   ├── base.py                BaseModelSerializer
│   ├── bookmark.py            BookmarkSerializer
│   ├── comic.py               ComicSerializer (covered by 01)
│   ├── groups.py              Publisher/Imprint/Series/Volume
│   ├── named.py               URLNamedModelSerializer family (248 LOC)
│   └── pycountry.py           CountrySerializer, LanguageSerializer
└── opds/
    ├── authentication.py
    ├── urls.py
    ├── v1.py                  OPDS1 entry/feed (73 LOC)
    └── v2/
        ├── facet.py
        ├── feed.py
        ├── links.py           OPDS2LinkSerializer (per-link SMF)
        ├── metadata.py
        ├── progression.py
        ├── publication.py     OPDS2PublicationSerializer (159 LOC)
        └── unused.py          Aspirational, not wired up
```

## Surface ranking by request volume

Hot paths first — order matters because the serializers on hot paths
multiply tiny costs by huge N:

| # | Endpoint | Serializer entry point | Cardinality | Sub-plan |
| -- | -------- | ---------------------- | ----------- | -------- |
| 1 | `/api/v3/<group>/<pks>/<page>` (browse) | `BrowserPageSerializer` → `BrowserCardSerializer` × N cards | 20–100 cards | [02](./02-browser.md) |
| 2 | `/api/v3/c/<pk>/metadata` | `MetadataSerializer` → 17 nested serializers | 1 row × deep nesting | [04](./04-models.md) |
| 3 | `/opds/v1.2/<group>/<pks>` | OPDS1 templated feed × N entries | 50–100 entries | [03](./03-opds.md) |
| 4 | `/opds/v2.0/<group>/<pks>` | `OPDS2FeedSerializer` × N publications | 50–100 publications | [03](./03-opds.md) |
| 5 | `/api/v3/c/<pk>/reader` | `ReaderComicsSerializer` | 1 reader open | [05](./05-auth-admin.md) |
| 6 | `/api/v3/<group>/<pks>/choices/<field>` | `BrowserChoicesFilterSerializer` | 1 menu × ~50 choices | [02](./02-browser.md) |
| 7 | `/api/v3/auth/flags` | `AuthAdminFlagsSerializer` | 1 dict × 4 fields | [05](./05-auth-admin.md) |
| 8 | `/api/v3/admin/stats` | `StatsSerializer` (cached 60s in PR #610) | 1 dict × deep nesting | [05](./05-auth-admin.md) |
| 9 | `/api/v3/admin/library` (list) | `LibrarySerializer` × N libraries | 5–50 libraries | [05](./05-auth-admin.md) |
| 10 | `/api/v3/admin/user` (list) | `UserSerializer` × N users | 1–10 users | [05](./05-auth-admin.md) |

## Cross-cutting themes

These patterns appear across multiple sub-plans; consolidating the
fix once pays off across surfaces:

### Theme A — Module-level caches for per-instance computation

Several `Field` and `Serializer` classes do work at *call time* that
could be cached at *module load time*:

- `PyCountryField.to_representation` runs `pycountry.countries.get()`
  per Comic per request. Built-in `pycountry` data is static — a
  module-level alpha_2 → name dict eliminates the per-call lookup.
- `BrowserChoicesFilterSerializer.get_choices` instantiates
  `BrowserSettingsFilterSerializer()` then walks `.get_fields()` per
  request. The fields dict is static; cache it at import.
- `SerializerChoicesField.__init__` instantiates a serializer just
  to read `.get_fields().keys()`. Per-class cache.

Detailed in [01-fields.md](./01-fields.md).

### Theme B — `source="foo.bar.baz"` chain depth

DRF `source="..."` resolves via `getattr` chain. Each hop is a free
read if the FK is loaded, but a SELECT if not. Across the codebase:

- 2-hop: `URLNamedModelSerializer.url = source="identifier.url"` —
  10 subclasses (CreditPerson, CreditRole, Character, Genre,
  Location, Story, StoryArc, Tag, Team, Universe). Default M2M
  optimizer in `query_intersections.py` already adds
  `select_related("identifier")` — covered for the metadata path.
- 3-hop: `StoryArcNumberSerializer.url =
  source="story_arc.identifier.url"`. Optimizer covers it via
  `prefetch_related("story_arc__identifier")`.
- 2-hop in admin: `GroupSerializer.exclude =
  source="groupauth.exclude"` — viewset has
  `select_related("groupauth")`, but no test enforces it.
- 2-hop in admin: `UserSerializer.last_active =
  source="userauth.updated_at"` and `age_rating_metron =
  source="userauth.age_rating_metron"` — viewset has the prefetch.

The risk isn't the current code — it's that the optimizer/queryset
contract isn't enforced. Suggested fix: a unit test that wraps each
hot-path serializer in `CaptureQueriesContext` and asserts query
count == 0. Detailed in each sub-plan.

### Theme C — Aspirational fields that aren't populated

`OPDS2PublicationMetadataSerializer` declares 10 contributor fields
(author, translator, editor, artist, illustrator, …) with
`many=True`, but the view's `_publication_metadata` only sets
`title`, `subtitle`, `published`, `modified`, `number_of_pages`. The
contributor fields are never populated, so they emit nothing.

This is a footgun: any future code that *does* populate those
fields will trigger an N+1 unless batching helpers are added in
parallel (the v1 path has `get_credit_people_by_comic` /
`get_m2m_objects_by_comic`; v2 has nothing equivalent).

Two ways to address: (a) delete the unused fields and add them back
when they're wired up; (b) add the v2 batching helpers preemptively
so the trap is closed. Detailed in [03-opds.md](./03-opds.md).

### Theme D — `SerializerMethodField` doing per-row computation

SMFs are the easiest spot to hide work. Some are unavoidable
(`get_admin_flags` for instance), but several do per-row Python
work that scales with response size:

- `BrowserAggregateSerializerMixin.get_mtime` parses every datetime
  string in `obj.updated_ats` via `datetime.strptime` per card. With
  20 cards × ~50 entries each, that's 1000+ `strptime` calls.
  Move to `datetime.fromisoformat` (faster) or push the max into
  SQL. Detailed in [02-browser.md](./02-browser.md).
- `OPDS2LinkSerializer.get_rel` does dict-get + isinstance-guard per
  link. With ~5 links per publication × 100 publications = 500
  calls per feed. Pre-compute `rel` into the link dict upstream and
  drop the SMF. Detailed in [03-opds.md](./03-opds.md).

### Theme E — Dead / unused code

Two clusters of unused serializers were found while auditing:

- `codex/serializers/auth.py:UserSerializer`,
  `UserCreateSerializer`, `UserLoginSerializer` — never imported
  anywhere. Includes a `get_admin_flags` SMF that fires
  `AdminFlag.objects.filter(...)` per call, but nothing calls it.
  Delete. Detailed in [05-auth-admin.md](./05-auth-admin.md).
- `codex/serializers/opds/v2/unused.py` — explicit (the filename
  itself says so). Convert to a module-level docstring with the
  class scaffolds in a `::` example block. Detailed in
  [03-opds.md](./03-opds.md).

## Methodology

For each finding the same loop:

1. **Capture baseline**. Use the existing perf harnesses:
   - `tests/perf/run_baseline.py` for browser flows
     (flow_a_browse_root, flow_c2_comic_metadata).
   - `tests/perf/run_opds_baseline.py` for OPDS v1 + v2.
   - `tests/perf/run_reader_baseline.py` for reader flows.
   Each has `--with-silk` for query-attribution traces.

2. **Wrap target serializer in `CaptureQueriesContext`**. Where
   possible, isolate the cost of `serializer.data` from view
   plumbing. Pattern:

   ```python
   from django.test.utils import CaptureQueriesContext
   from django.db import connection

   with CaptureQueriesContext(connection) as ctx:
       data = serializer.data
   print(len(ctx.captured_queries))
   ```

3. **Apply the fix**.

4. **Re-capture baseline + query count**. Confirm improvement on
   the targeted endpoint; confirm no regression on adjacent ones
   (e.g. browser changes shouldn't slow down OPDS).

5. **Land as a small commit** with cold/warm timings + query count
   before/after in the commit message.

## Suggested ordering

The sub-plans are numbered in implementation order — biggest
payoff per LOC first:

1. **[01-fields.md](./01-fields.md) — Fields cleanups.**
   Country/language import-strip audit, `PyCountryField` cache,
   drop sanitization from ISO codes. Touches every Comic
   serialization path. Cheap, high-leverage.
2. **[02-browser.md](./02-browser.md) — Browser serializers.**
   Browser cards are the highest-N surface (browse list =
   50–100 cards × 30+ fields each). Mtime parsing + choices
   instantiation are the visible offenders.
3. **[03-opds.md](./03-opds.md) — OPDS v1 + v2.** Wire v2
   batching helpers parallel to v1 and populate the declared
   contributor fields, drop the per-link `get_rel` SMF, convert
   `unused.py` into docstring scaffolds.
4. **[04-models.md](./04-models.md) — Models / metadata.**
   Stage 5e handoff carries this forward. Confirm zero
   serializer-time queries on the metadata pane.
5. **[05-auth-admin.md](./05-auth-admin.md) — Auth + admin.**
   Dead-code cleanup in `auth.py`, add prefetch enforcement
   tests for admin list endpoints.

Each sub-plan yields one PR (or a single bundled PR if the diffs
stay small, like `cover-cleanup`).

## Risks

- **Caching surface drift.** Module-level caches (Theme A) can
  shadow updates if upstream data changes (e.g. pycountry version
  bump). Pin the cache build to import time and let server restart
  invalidate.
- **Source-chain assumption tests.** Adding `assertNumQueries` to
  the test suite locks in viewset-prefetch contracts. If a future
  refactor splits the queryset and the prefetch, the test will
  catch it — that's the point — but be ready to update tests that
  intentionally remove a prefetch.
- **OPDS v2 contributor-field population** changes the response
  body shape (previously-empty fields suddenly contain arrays).
  drf-spectacular's OpenAPI schema is unchanged — the fields were
  already declared. Clients that ignored unknown / empty fields
  are unaffected. Mitigation: roll out behind the existing
  OPDS-client testing gate from PR #606 (cover cleanup).

## Out of scope

- **Renderer-level optimization** (DRF's JSONRenderer, OPDS XML
  renderer). Possibly a future project; serializer-side fixes are
  cheaper to land first.
- **Switching to alternative serializer libraries** (drf-pydantic,
  marshmallow, …). Out of scope; project-wide rewrite.
- **Per-endpoint response caching beyond `/admin/stats`** (already
  cached in PR #610 for 60s). Caching browser/metadata responses
  cross-request needs invalidation infrastructure that doesn't
  exist yet.

## Sub-plans

- [01-fields.md](./01-fields.md) — Country/language strip audit,
  `PyCountryField` cache, drop `SanitizedCharField` from ISO codes,
  `SerializerChoicesField` per-instance cost, vuetify field audit.
- [02-browser.md](./02-browser.md) — Browser endpoint serializers
  (`BrowserCardSerializer`, `BrowserChoicesFilterSerializer`,
  `BrowserAggregateSerializerMixin.get_mtime`).
- [03-opds.md](./03-opds.md) — OPDS v1 audit + v2 batching wired
  with contributor-field population, per-link `get_rel` SMF
  removal, `unused.py` → docstring scaffolds.
- [04-models.md](./04-models.md) — Model serializers + the
  `ComicSerializer` / `MetadataSerializer` audit absorbed from
  `tasks/browser-views-perf/stage5e-handoff-serializer-audit.md`.
- [05-auth-admin.md](./05-auth-admin.md) — `auth.py` dead code,
  admin list FK source chains, `LibrarySerializer.validate_path`.
