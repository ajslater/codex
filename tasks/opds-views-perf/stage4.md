# Stage 4 — v1 acquisition M2M batching + progression PUT conflict detection

Closes Phase E from
[99-summary.md §3](99-summary.md#3-suggested-landing-order):

- **Tier 2 #7** — batch v1 entry M2M fan-out (`category_groups` /
  `authors` / `contributors`) on multi-comic acquisition feeds.
- **Tier 2 #8** — fold the dead progression PUT conflict pre-check
  into a single atomic conditional UPDATE; surface real spec-compliant
  409 responses on multi-device sync conflicts.

## Headline

`v1_acquisition_with_metadata` (full-feed render, 106 entries):
**817 → 20 cold queries (-797, ~40× reduction)**, 1585 → 154 ms
cold wall (~10× reduction).

The harness's `v1_acquisition_with_metadata` row reflects the
[perf-user state artifact documented in
stage0.md](stage0.md#harness-reproducibility-note) — depending on the
warm-up loop's order, the URL renders either the 7-entry navigation
shell (16 cold queries) or the 106-entry full feed (817 cold queries
pre-fix). The headline number above was captured in a controlled
full-feed-state run (manually setting `top_group=s` + `order_by=sort_name`
on the perf user before the request); the harness's shell-mode rows
are unchanged before/after the fix.

| Flow                                                | Cold queries (before → after)    | Cold wall (before → after) |
| --------------------------------------------------- | -------------------------------: | -------------------------: |
| **v1_acquisition_with_metadata** (full-feed)        | **817 → 20**                     | **1585 → 154 ms**          |
| v1_acquisition_with_metadata (harness/shell mode)   |                          16 → 16 |             45 → 47 ms     |
| (other 10 flows)                                    |                 within ±0 noise  |                            |

Artifacts:

- `tasks/opds-views-perf/stage4-before.json` — captured against
  post-Stage-3 HEAD.
- `tasks/opds-views-perf/stage4-after.json` — captured with both
  fixes applied.

## What landed

### #7 — Per-page batching of v1 entry M2M fan-out

Three new helpers in `codex/views/opds/metadata.py`:

```python
def get_credit_people_by_comic(comic_pks, roles, *, exclude) -> dict[int, list]:
    """Per-comic mapping of distinct credit people. One query."""

def get_m2m_objects_by_comic(comic_pks) -> dict[int, dict[str, list]]:
    """Per-comic mapping of M2M items grouped by model name. One UNION query."""
```

`get_credit_people_by_comic` collapses the per-entry `CreditPerson`
filter (annotates `_comic_id` from `credit__comic`, partitions in
Python, attaches the OPDS facet URL via `_credit_url_for`).

`get_m2m_objects_by_comic` UNIONs all 7 `OPDS_M2M_MODELS` tables
into one query keyed by `(_comic_id, _kind)` and partitions in
Python — same UNION shape Stage 1 used for the v2 manifest's
`_publication_subject`. SQLite `UNION ALL` works cleanly with
Django's `QuerySet.union()`.

`OPDS1EntryData` (`codex/views/opds/v1/const.py`) gains three
optional fields — `authors_by_pk`, `contributors_by_pk`,
`category_groups_by_pk` — passed through `OPDS1EntryLinksMixin.__init__`
into per-entry `_authors_by_pk` etc. attributes. The
`OPDS1Entry.{authors,contributors,category_groups}` properties read
the batched dict when present and fall back to the legacy per-entry
single-comic helper otherwise (so facet entries / single-comic
acquisition feeds still work).

`OPDS1FeedView._get_entries_section` populates the dicts when
`metadata=True` and `key=="books"`:

```python
if metadata and key == "books":
    all_pks = [obj.pk for obj in objs]
    authors_by_pk = get_credit_people_by_comic(all_pks, AUTHOR_ROLES, exclude=False)
    contributors_by_pk = get_credit_people_by_comic(all_pks, AUTHOR_ROLES, exclude=True)
    category_groups_by_pk = get_m2m_objects_by_comic(all_pks)
```

3 queries total per page replace the previous `9 × N_entries`. On the
106-entry "All Batman" series with `?opdsMetadata=1`, that's 954
queries → 3 queries.

### #8 — Progression PUT atomic conditional UPDATE

Two changes:

1. **Serializer** (`codex/serializers/opds/v2/progression.py`):
   `modified = DateTimeField(read_only=True)` → `required=False`. The
   read-only declaration silently dropped the field from PUT input
   validation, making the previous conflict pre-check unreachable
   (zero progression-related queries fired on PUT today). The new
   declaration is read+write; clients echoing `modified` from a GET
   response now see it accepted.
2. **View** (`codex/views/opds/v2/progression.py:put`): replaced the
   dead `_get_bookmark_query() + qs.first()` round-trip with a
   single atomic conditional UPDATE:
   ```python
   updated_count = Bookmark.objects.filter(
       **bookmark_filter, updated_at__lte=new_modified
   ).update(page=page, updated_at=timezone.now())
   if updated_count:
       return Response(status=HTTPStatus.OK)
   if Bookmark.objects.filter(**bookmark_filter).exists():
       return Response(status=HTTPStatus.CONFLICT)
   self.update_bookmark()  # async create path
   return Response(status=HTTPStatus.OK)
   ```
   The `updated_at__lte=new_modified` predicate scopes the UPDATE to
   only the case where the DB's bookmark is at-or-before the client's
   echo. If the UPDATE matches a row, the write succeeds in one
   query. If 0 rows match AND a bookmark exists, the DB has a fresher
   row than the client's echo — real conflict, return 409. If 0 rows
   match AND no bookmark exists, fall through to the existing async
   `update_bookmark` path (first-time write).

When clients don't echo `modified` (older OPDS clients, single-device
sync), the `if new_modified is None` branch keeps the prior liberal
"always update" behavior via the async task — preserving backward
compatibility.

Functional verification (run interactively against the dev DB):

| Scenario                                         | Status |
| ------------------------------------------------ | -----: |
| PUT no `modified` (no bookmark exists)           |    200 |
| PUT with `modified` older than DB bookmark       |    409 |
| PUT with `modified` matching/newer than DB row   |    200 |

Behavior change (documented for downstream): clients that previously
sent stale `modified` and got silent 200s now receive 409. The spec
calls for this — and OPDS 2 reader apps generally handle 409 by
re-fetching the GET to re-sync local state. If a client is broken in
a way that this behavior change regresses, the same client was
already losing progression updates silently before this fix and is
now correctly seeing them rejected.

## Verification

- **`make test`** — 24 / 24 pass.
- **`make lint`** — Python lint passes; pre-existing remark warning
  on plan markdown unchanged.
- **Functional smoke**: 3-case progression PUT exercise above.
- **Forced-state v1_acquisition_with_metadata**: 817 → 20 cold
  queries with full-feed render verified.
- **Manifest spot-check** (M2M + credits output unchanged): same
  authors / contributors / categories counts as Stage 3 baseline.

## Out-of-scope follow-ups (still on plan)

- A regression test suite for OPDS endpoints. The current `tests/`
  layout doesn't include OPDS coverage; the harness in
  `tests/perf/run_opds_baseline.py` is for benchmarking, not
  correctness assertion. Adding a `tests/test_opds_progression.py`
  with the 3-case conflict matrix and a `tests/test_opds_v1_feed.py`
  for the metadata=True path is a clean follow-up.
- Plan #19 — cachalot tagging for Bookmark writes. Progression PUT
  now fires synchronous UPDATE on the conflict path (1 query) plus
  the existing async create path. cachalot will invalidate the
  Bookmark cache on every UPDATE; if PUT volume is high enough to
  matter, tagging Bookmark with cachalot-skip would be the next
  optimization.

## What's next

- **Phase F** — Tier 3-4 cleanups:
  - **#10** — Resolve `opds:bin:page` URL once for
    `_publication_reading_order` (per-page reverse() in the manifest).
  - **#11** — Cache parsed `request.GET["filters"]` JSON.
  - **#14** — Cache resolved URL templates per `url_name`.
  - **#16** — Verify and add `select_related("parent_folder")` on
    the manifest book queryset.
  - **#18** — Refactor `_add_url_to_obj` mutation pattern (now
    largely superseded by Stage 4's batched helpers).
