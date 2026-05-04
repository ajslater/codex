# Stage 1 — Manifest credit + subject batching

Closes Phase C of the plan in
[99-summary.md §3](99-summary.md#3-suggested-landing-order). Both Tier 1
manifest items land:

- **Tier 1 #2** — batch `_publication_credits` (11 → 1 query, plus the
  7 lazy `credit.person` FK queries that materialized via
  `_add_tag_link` collapse into the same join).
- **Tier 2 #5** — batch `_publication_subject` (7 → 1 UNION query).

## Headline

`v2_manifest`: **47 → 24 cold queries (-23, ~49% reduction)**, 113 →
87 ms cold wall (-26 ms).

| Flow                         | Cold queries (before → after) | Cold wall (before → after) |
| ---------------------------- | ----------------------------: | -------------------------: |
| v2_manifest                  |                  **47 → 24**  |       **113 → 87 ms**      |
| v1_start                     |                       14 → 14 |             53 → 49 ms     |
| v1_root_browse               |                       15 → 15 |            121 → 126 ms    |
| v1_series_acquisition        |                       18 → 18 |             50 → 53 ms     |
| v1_acquisition_with_metadata |                       16 → 16 |             45 → 49 ms (¹) |
| v1_opensearch                |                         3 → 3 |              5 → 6 ms      |
| v2_start                     |                       53 → 53 |            502 → 508 ms    |
| v2_root_browse               |                       15 → 15 |            110 → 112 ms    |
| v2_series_publications       |                       18 → 18 |             50 → 49 ms     |
| v2_progression_get           |                         9 → 9 |             14 → 15 ms     |
| auth_doc_v1                  |                         2 → 2 |              6 → 5 ms      |

¹ The `v1_acquisition_with_metadata` row reflects the perf-user state
artifact documented in [`stage0.md` §
"Harness reproducibility note"](stage0.md#harness-reproducibility-note);
the headline 817-query fan-out captured in `baseline.json` reproduces
when the user has its full settings restored, but is unrelated to
Stage 1's manifest scope.

Artifacts:

- `tasks/opds-views-perf/stage1-before.json` — captured against
  `origin/v1.11-performance` (post-Stage-0 HEAD).
- `tasks/opds-views-perf/stage1-after.json` — captured with both
  Phase C fixes applied.

## What landed

### #2 — `_publication_credits` batched into one query

`codex/views/opds/v2/manifest.py:_publication_credits`. The prior
implementation looped `_MD_CREDIT_MAP` (11 keys) and fired one
`Credit.objects.filter(comic__in=..., role__name__in=role_set)`
per key — 11 queries even when most role-sets returned empty. On
top of that, `_add_tag_link(credit, "credits", "person")` accessed
`credit.person` lazily, triggering an additional `CreditPerson.get`
per credit returned. On the dev DB's `comic_pk=10785` (7 credits
across 6 roles), the silk SQL trace showed **11 Credit + 7
CreditPerson = 18 queries** for credits alone.

The batched implementation pulls every credit for the comic in a
single query with `select_related("person", "role")`, then partitions
in Python by `role.name` against the `_MD_CREDIT_MAP` role-sets:

```python
all_credits = list(
    Credit.objects.filter(comic__in=obj.ids)
    .select_related("person", "role")
    .annotate(name=F("person__name"), role_name=F("role__name"))
)
by_role: dict[str, list[Credit]] = {}
for credit in all_credits:
    by_role.setdefault(credit.role_name, []).append(credit)

credit_md: dict[str, tuple[Credit, ...]] = {}
for key, roles in _MD_CREDIT_MAP.items():
    bucket = [c for role in roles for c in by_role.get(role, [])]
    if not bucket:
        continue
    for credit in bucket:
        self._add_tag_link(credit, "credits", "person")
    credit_md[key] = tuple(bucket)
return credit_md
```

The role-sets in `_MD_CREDIT_MAP` are disjoint (each role appears in
at most one set), so no de-duplication is needed in the partition
step. The annotated `name` / `role_name` attributes are preserved so
the existing `OPDS2ContributorSerializer` (which reads `name`,
`links`, `role` via `source="role_name"`) continues to render
unchanged.

Removed the now-unused `_add_credits` private method and the
`get_credits` helper in `codex/views/opds/metadata.py`. `get_credits`
had no other callers.

### #5 — `_publication_subject` UNION batch

`codex/views/opds/v2/manifest.py:_publication_subject`. The prior
implementation called `get_m2m_objects(obj.ids)` (in
`codex/views/opds/metadata.py`) which loops `OPDS_M2M_MODELS` (7
models — Character, Genre, Location, SeriesGroup, StoryArc, Tag,
Team) and builds one queryset per model. Each was materialized in
the inner `for subj in subjs:` loop → **7 queries per manifest**.

Replaced with a single `UNION ALL` over `(pk, name, _kind)` tuples:

```python
queries = []
for model in OPDS_M2M_MODELS:
    rel = GroupACLMixin.get_rel_prefix(model)
    kind = model.__name__.lower()
    q = (
        model.objects.filter(**{rel + "in": obj.ids})
        .annotate(_kind=Value(kind, output_field=CharField()))
        .values("pk", "name", "_kind")
    )
    queries.append(q)
rows = queries[0].union(*queries[1:], all=True).order_by("_kind", "name")
```

Iteration over `rows` materializes one query that returns all subject
rows across all seven kinds. The rows come back as `dict`s; reconstructed
into `SimpleNamespace(pk, name, links)` so `_add_tag_link` (which uses
`obj.pk` / `obj.name` and mutates `obj.links`) and the downstream
`OPDS2SubjectSerializer` (which reads `name` / `links`) work unchanged.

`get_m2m_objects` is still exported from `codex/views/opds/metadata.py`
because the v1 entry path (`codex/views/opds/v1/entry/entry.py:152`)
still uses it. Only manifest stops calling it.

Order is preserved: `OPDS_M2M_MODELS` is in alphabetical order when
lowercased, so `order_by("_kind", "name")` produces the same flat
sequence the prior nested-loop produced.

### Drive-by — drop unused `get_credits`

`codex/views/opds/metadata.py`. After #2, `get_credits` had no
remaining callers (the only one was `_add_credits` which was inlined
into the batched `_publication_credits`). Removed along with the
now-unused `Credit` and `F` imports + `from django.db.models.query
import QuerySet`.

## Surfaced bug — `peniciller` typo (NOT fixed here)

`codex/serializers/opds/v2/publication.py:95` declares the field as
`peniciller = OPDS2ContributorSerializer(...)` (typo). This silently
drops penciller credits from manifest responses: the role bucket is
emitted as `"penciller"` by `_publication_credits` (matching the
`_MD_CREDIT_MAP` key), but DRF can't find a serializer field with
that name and discards the payload.

The pre-existing behavior is preserved by Stage 1 — both before and
after the batching, penciller credits do not surface in responses.
Spawned a separate follow-up task to fix the typo cleanly with a
behavior-change PR.

## Verification

- `make test` — 24 / 24 pass.
- `make lint` — Python lint passes; same pre-existing remark warning
  on plan markdown files reproduces unchanged.
- Manifest JSON spot-checked against `comic_pk=10785`: 374 subjects,
  6 credit-bucket entries (author, artist, letterer, colorist, inker,
  + the dropped-due-to-serializer-typo penciller), all role/name/
  links structures intact.

## What's next

- Phase D — caching (Tier 1 #1) + start-page batching (Tier 1 #4).
  Highest impact, highest risk; unblocks once R1's `Vary: Cookie,
  Authorization` story is verified end-to-end on feed routes.
- Phase E — progression PUT conditional update (Tier 2 #8) and v1
  acquisition M2M batch (Tier 2 #7). Smaller volume but mechanical
  wins.
