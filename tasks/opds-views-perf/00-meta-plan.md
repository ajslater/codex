# Codex `codex/views/opds/` — Performance Plan: Methodology

How this analysis is organized. Mirrors the structure of the
`tasks/browser-views-perf/` plan; the goal is to produce a comparable
ranked backlog for the OPDS subsystem.

## Scope

Everything under `codex/views/opds/` (33 files, ~3,700 LOC), plus the
URL configuration in `codex/urls/opds/` and the timeout constants in
`codex/urls/const.py`. Cover/page/download endpoints exposed via
`codex/views/opds/binary.py` are in scope for the routing/cache layer
but not for cover-pipeline rework — that work was absorbed into Stage 3
+ Stage 5a of the browser-views perf project and the OPDS routes
already use the same per-pk cover endpoints.

Out of scope (matches browser plan):

- Reader views (`codex/views/reader/`).
- Admin views, auth views, the librarian daemon.
- Frontend OPDS clients.
- DRF / Django framework upgrades.
- Wholesale schema changes.

## Why now

The browser-views perf project (`tasks/browser-views-perf/`) closed
Stage 5 with all four Tier 1 items landed and the bulk of Tier 2-3
done. `OPDSBrowserView` extends `BrowserView` directly, so most of
those wins flow through to OPDS for free. What remains is what OPDS
itself adds on top — and the audit below shows that's substantial.

## Inputs to the audit

- `codex/views/opds/**/*.py` — 33 files, walked top-to-bottom by
  decreasing line count. Inheritance graph traced to understand which
  BrowserView pipeline stages each OPDS view actually exercises.
- `codex/urls/opds/**/*.py` — route topology, `cache_page` wrapping,
  timeout constants.
- `codex/serializers/opds/**/*.py` — read for context on what each view
  is required to produce. Not scoped for changes here.
- The browser-views perf landing record (`tasks/browser-views-perf/`)
  — used to identify which OPDS hotspots are already mitigated by
  inherited BrowserView work and which are genuinely new.
- No production benchmarks. Every claim in this plan is "audit-grade"
  — file:line citations and qualitative cost shape — and must be
  confirmed with an OPDS-specific harness (see Phase A in the summary)
  before any Tier 1 implementation work lands.

## Cost-shape vocabulary

Same calibration as the browser plan, repeated here so the sub-plans
read consistently:

- **Hot loop** — code that iterates per-entry, per-publication, or
  per-group on a feed page. A 50-comic page makes a 1 ms operation a
  50 ms wall-time line.
- **N queries per request** — one query per outer iteration, no
  prefetch / no batching.
- **Repeated work per request** — two or more code paths recompute
  the same value (timestamp, AdminFlag fetch, etc.) without sharing
  state.
- **Read-path write** — a Django model write fired from a GET handler.
  Causes cachalot row invalidation in addition to the write itself.
  Every browser plan note about this applies to OPDS too — the
  progression PUT path is the obvious one, but worth tagging.
- **Cache-misuse** — `cache_page` wrapping that's effectively a no-op
  because the timeout is 0, or that varies on a header that defeats
  the cache key.

## Sub-plan layout

| File                                                     | Scope                                                                            |
| -------------------------------------------------------- | -------------------------------------------------------------------------------- |
| [`01-routes-and-cache.md`](01-routes-and-cache.md)       | `OPDS_TIMEOUT = 0`, `cache_page` topology, all OPDS routes                       |
| [`02-feed-pipeline.md`](02-feed-pipeline.md)             | v1 + v2 main feed views, BrowserView reuse, preview pipeline re-runs             |
| [`03-entry-serialization-v1.md`](03-entry-serialization-v1.md) | `v1/entry/` — title, links, `lazy_metadata`, M2M per-entry                |
| [`04-publications-v2.md`](04-publications-v2.md)         | `v2/feed/` — `_publication`, `_thumb`, `get_publications_preview`, group assembly |
| [`05-manifest.md`](05-manifest.md)                       | `v2/manifest.py` — credit fan-out, reading_order, identifiers, story_arcs        |
| [`06-progression-binary-aux.md`](06-progression-binary-aux.md) | progression GET/PUT, binary endpoints, opensearch, authentication doc      |
| [`99-summary.md`](99-summary.md)                         | Roll-up: ranked backlog, suggested landing order, cross-cutting guidance         |

## Methodology per sub-plan

For each file in scope:

1. **Purpose** — one sentence covering what the view exists to do.
2. **Per-request cost shape** — query count (when known), hot loops,
   repeated work. Lazy-property and lazy-queryset patterns get an
   explicit "fires when consumed by serializer X" note so the cost is
   not invisible to the audit.
3. **Hotspots** — file:line references with a one-paragraph
   reproduction of what's expensive and why.
4. **Interactions with `BrowserView`** — what the OPDS view inherits,
   what it overrides, and what extra work it layers on top.

Sub-plans 01-06 stop at audit. Implementation strategy lives in
`99-summary.md` so the ranked backlog reads as a single ordered list
rather than scattered across files.

## What changed from the browser-views audit

Two methodology adjustments compared to the browser plan:

- **No file-by-file walkthrough of files under 30 LOC unless they're
  load-bearing.** The browser plan noted but didn't deeply analyze
  trivially small files. OPDS has more of them (constants modules,
  thin mixin classes), so they're listed in `01-routes-and-cache.md`
  for orientation only.
- **`Status` column lives in `99-summary.md` from day one.** The
  browser plan added it retroactively after Stage 5d. For OPDS,
  every backlog item is born with an explicit ⏳ Open status so the
  document doesn't need a retroactive sweep at the end.

## Exit criteria for the audit phase

Before any Tier 1 OPDS implementation work begins, confirm:

- [ ] An OPDS-specific perf harness exists (mirrors
      `tasks/browser-views-perf/measure-perf` flows). Minimum flows:
      v1 root, v1 deep, v2 root, v2 deep, v2 manifest single-comic,
      v2 progression GET, v2 progression PUT.
- [ ] Cold + warm baselines recorded for each flow.
- [ ] The `OPDS_TIMEOUT = 0` decision has an explicit rationale
      written down (this plan's 01 sub-plan flags it; the rationale
      itself needs to be sourced from git history + auth analysis).

Once those three are in place, the Tier 1 backlog can be scheduled.
