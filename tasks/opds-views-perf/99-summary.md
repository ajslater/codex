# Codex `codex/views/opds/` — Performance Plan

A prioritized, sequenced plan for improving the performance of every
view under `codex/views/opds/` while preserving existing behavior.
Based on a file-by-file audit of ~3,700 lines across 33 files, plus
the OPDS routing layer in `codex/urls/opds/`. Broken out into six
sub-plans:

- [`00-meta-plan.md`](00-meta-plan.md) — methodology
- [`01-routes-and-cache.md`](01-routes-and-cache.md) — `OPDS_TIMEOUT = 0`,
  `cache_page` topology, all OPDS routes
- [`02-feed-pipeline.md`](02-feed-pipeline.md) — main v1 + v2 feed
  views, BrowserView reuse, preview pipeline re-runs
- [`03-entry-serialization-v1.md`](03-entry-serialization-v1.md) —
  `v1/entry/`: `lazy_metadata`, M2M per-entry, link generation
- [`04-publications-v2.md`](04-publications-v2.md) — `v2/feed/`:
  `_publication`, `_thumb`, `get_publications_preview`
- [`05-manifest.md`](05-manifest.md) — `v2/manifest.py`: credit
  fan-out, reading_order, identifiers, story_arcs
- [`06-progression-binary-aux.md`](06-progression-binary-aux.md) —
  read-position writes, binary endpoints, opensearch, auth doc

This document rolls all sub-plan findings into one ordered backlog.
Each item cites the sub-plan for the detailed "why" and code-level
specifics.

---

## 1. Executive summary — where the time is going

OPDS inherits the full BrowserView pipeline from
`codex/views/browser/`. The browser-views perf project (Stage 0
through Stage 5d, Sept 2025–April 2026) closed 27 of 31 backlog
items; those wins flow through to OPDS automatically because
`OPDSBrowserView` extends `BrowserView`.

That leaves three categories of OPDS-specific cost:

1. **Caching at the route layer is currently disabled.**
   `OPDS_TIMEOUT = 0` makes every `cache_page` wrap on every OPDS
   feed/manifest/opensearch/auth-doc/start route a no-op. The
   commented-out `# BROWSER_TIMEOUT` in `codex/urls/const.py:7`
   suggests it was once `60 * 5` and got disabled — the *why* needs
   to be reconstructed from git history before re-enabling. If this
   single item lands, it dwarfs everything else in the plan.

2. **Per-publication / per-entry serialization layered on top of the
   browser pipeline.** v2 manifest fires up to **20 queries per
   manifest** for credits + M2M subjects + story arcs (sub-plan 05).
   v1 acquisition entries fire **9 queries per entry** for
   author/contributor/category-group fan-out (sub-plan 03). Both
   paths are batchable; both are gated on the `metadata=True` flag,
   which changes how often they fire in practice.

3. **Start-page preview pipeline re-runs.** `get_publications_preview`
   instantiates a fresh feed view per `PREVIEW_GROUPS` link spec
   (~5 entries) and runs the full filter pipeline against each
   (sub-plan 02 #2 / sub-plan 04 #3). Five full pipeline cascades
   on every start-page hit, on top of the main feed assembly.

Secondary cost centers (see ranked backlog):

4. **Uncached AdminFlag query inside `is_allowed`** static method
   bypasses the request-cached `admin_flags` MappingProxyType.
5. **`Comicbox` opens on the request thread** when
   `lazy_metadata()` finds missing page_count/file_type. Async
   re-import is queued, but the synchronous open is a per-request
   disk hit.
6. **Bookmark progression PUT** pre-fetches a row for conflict
   detection, then writes (two queries per PUT). Plus cachalot
   invalidation on every progression sync.
7. **Per-page `reverse()` in manifest reading_order** for
   high-page-count comics (PDFs can have 500+ pages).

---

## 2. Ranked backlog

Each row includes severity, estimated effort, risk, and a link to
the sub-plan with the code-level analysis. Status is **all-open** at
this point — no implementation has started. Use ⏳ Open until items
land.

### Tier 1 — critical latency wins

| #   | Change | Sub-plan | Impact | Effort | Risk | Status |
| --- | ------ | -------- | ------ | ------ | ---- | ------ |
| 1   | **Re-enable OPDS route caching.** Set `OPDS_TIMEOUT > 0` (suggest 60 s). Confirm `Vary: Cookie, Authorization` is set on feed routes (binary routes already have it — `codex/urls/opds/binary.py:36-37`). Investigation phase: source the original disable rationale from git history first. | 01 #1 | **Very high** (every feed request currently re-runs the full pipeline) | M | M-H | ✅ Stage 2 |
| 2   | **Batch `_publication_credits` into a single query.** Replace the 11-query loop in `v2/manifest.py:194-199` with one `Credit.objects.filter(comic__in=obj.ids)` + Python-side partition by role name. | 05 #1 | **High** (saves 10 queries per manifest hit) | S-M | L | ✅ Stage 1 |
| 3   | **Fix N+1 in `_publication_belongs_to_story_arcs`.** Change `.only("story_arc", "number")` → `.select_related("story_arc")` (or `.values("story_arc__pk", "story_arc__name", "number")`) in `v2/manifest.py:122-144`. | 05 #2 | **Medium-High** (textbook N+1 on every manifest hit; cost scales with story-arc count) | XS | L | ✅ Stage 0 |
| 4   | **Skip preview-pipeline re-runs on start page.** `v2/feed/publications.py:240-269` re-instantiates a feed view + runs the full ACL/filter/annotation pipeline per `PREVIEW_GROUPS` link spec. Either batch into a single union query or memoize ACL+annotation results at the view level. | 02 #2, 04 #3 | **Medium-High** (saves ~4 full pipeline runs per start-page hit) | M-L | M | ✅ Stage 3 (cache-share variant; UNION-batch alternative deferred) |

### Tier 2 — redundant work on every request

| #   | Change | Sub-plan | Impact | Effort | Risk | Status |
| --- | ------ | -------- | ------ | ------ | ---- | ------ |
| 5   | **Batch `_publication_subject` M2M loop.** Replace `get_m2m_objects` 7-query loop with a UNION query or `prefetch_related` on the manifest book queryset. `metadata.py:50-60` + `v2/manifest.py:176-184`. | 05 #3 | High (saves 6 queries per manifest hit) | M | M | ✅ Stage 1 |
| 6   | **Convert `is_allowed` from static method to instance method that reads `self.admin_flags["folder_view"]`.** Eliminates the uncached `AdminFlag.objects.get(...)` query at `v2/feed/publications.py:35-56`. Same anti-pattern at `v1/facets.py:158-164` — fix together. | 02 #6, 04 #2 | Medium (per-link AdminFlag query collapses to a dict lookup) | S | L | ✅ Stage 0 |
| 7   | **Batch v1 entry M2M fan-out for acquisition feeds.** When `metadata=True` on a multi-book feed, `category_groups` / `authors` / `contributors` produce 9 queries per entry. Replace per-entry calls with per-page batched calls. `v1/entry/entry.py:131-152` + `metadata.py`. | 03 #1 | Medium (high if multi-book acquisition feeds are common; needs traffic data to confirm) | M | M | ⏳ Open |
| 8   | **Drop conflict pre-check on progression PUT.** Replace the `qs.first()` + Python comparison with a conditional `UPDATE` in `update_bookmark()` itself. `v2/progression.py:200-229`. | 06 #1, 06 #3 | Medium (saves 1 query + 1 ACL filter computation per progression sync) | S-M | M | ⏳ Open |

### Tier 3 — batch-shaped redundancies

| #   | Change | Sub-plan | Impact | Effort | Risk | Status |
| --- | ------ | -------- | ------ | ------ | ---- | ------ |
| 9   | **Defer `lazy_metadata` Comicbox open.** When `obj.page_count` or `obj.file_type` is missing, the v1 stream link currently opens the comic file synchronously. Async re-import is already queued — emit a degraded link (or omit) and let the next request render correctly. `v1/entry/links.py:120-128, 140`. | 03 #2 | Medium (only fires for missing-metadata comics; rare in steady state, common after fresh import) | S | M | ⏳ Open |
| 10  | **Resolve `opds:bin:page` URL once for `_publication_reading_order`.** Replace the per-page `reverse()` call with a format-string build outside the loop. `v2/manifest.py:231-259`. | 05 #4 | Medium for high-page-count comics (>100 pages); low otherwise | S | L | ⏳ Open |
| 11  | **Cache parsed `request.GET["filters"]` JSON.** Currently parsed in `_subtitle_filters` (`v2/feed/__init__.py:35-55`) plus elsewhere in the BrowserView pipeline. Memoize on `self._parsed_filters` once. | 02 #5 | Low-Medium (sub-millisecond per call; cumulative if filters JSON is large) | S | L | ⏳ Open |
| 12  | **Replace `_update_feed_modified` nested-loop scan with `mtime` from `_get_group_and_books`.** The browser pipeline already produces the max mtime; v2 start view rescans the assembled feed redundantly. `v2/feed/__init__.py:193-204`. | 02 #1 | Low (eliminates duplicate timestamp computation; mostly cleanup) | XS | L | ⏳ Open |

### Tier 4 — clean-ups / small wins

| #   | Change | Sub-plan | Impact | Effort | Risk | Status |
| --- | ------ | -------- | ------ | ------ | ---- | ------ |
| 13  | **Extract `_obj_ts(obj) -> int` helper.** `floor(datetime.timestamp(obj.updated_at))` appears at 6 sites across `v2/feed/publications.py:145` and `v2/manifest.py:101, 117, 137, 240, 265`. Pure refactor, no perf delta on its own. | 04 #4, 05 #6 | Trivial | XS | L | ✅ Stage 0 |
| 14  | **Cache resolved URL templates per `url_name`.** ~5 `reverse()` calls per v1 entry × 50 entries × multiple OPDS sessions. Module-level dict `{"opds:bin:cover": "/o/bin/c/{pk}/cover.webp"}` plus f-string format would cut to a single dict lookup + format. | 03 #3 | Low (visible only as a cumulative >5 ms/page, if at all) | S | L | ⏳ Open |
| 15  | **Remove dead expression** at `v2/progression.py:226` (`max(position - 1, 0)` with no assignment). Code-health bug. | 06 #1 | Trivial | XS | L | ✅ Stage 0 |
| 16  | **Verify and add `select_related("parent_folder")`** on the manifest book queryset. `_publication_belongs_to_folder` reads `obj.parent_folder.path` — confirm whether the FK is fetched as part of `get_book_qs()` first. `v2/manifest.py:109-120`. | 05 #8 | Unknown — needs verification | S | L | ⏳ Open |
| 17  | **Verify and add `select_related("language")`** on the v2 publications book queryset. `_publication_metadata` reads `obj.language.name`; v1 already does this in `v1/facets.py:64`. | 02 #3 | Low (likely already covered by browser annotations) | XS | L | ✅ Stage 3 (also adds `volume` — was the bigger N+1) |
| 18  | **Refactor `_add_url_to_obj` mutation pattern.** `v1/entry/entry.py:118-129` mutates queryset model instances to attach a `url` attribute. Works fine but fragile — cachalot reuses model instances in principle. Code-health, not perf. | 03 #4 | Code health, not perf | S | L | ⏳ Open |
| 19  | **Audit `OPDS2ProgressionView` cachalot tagging.** Bookmark progression PUTs are high-frequency; consider tagging Bookmark writes with cachalot-skip so progression sync doesn't churn the cache for read paths that don't care about per-user state. | 06 #1 | Medium aggregate cost on installs with many active readers | M | M | ⏳ Open |

### Tier 5 — high-risk / needs investigation before scheduling

| #   | Item | Sub-plan | Status |
| --- | ---- | -------- | ------ |
| R1  | **`OPDS_TIMEOUT` rationale.** The disable was deliberate at some point. Surface the original reason via `git log -p codex/urls/const.py` and a scan of the OPDS issue tracker before scheduling Tier 1 #1. May reveal correctness issues (e.g., per-user data leaking across cache, or cookie-based auth not varying correctly). | 01 #1 | ✅ Stage 0 ([stage0.md](stage0.md#r1--opds_timeout--0-rationale)) |
| R2  | **OPDS-specific perf harness.** No baseline data exists for OPDS endpoints. The browser-views project built `tasks/browser-views-perf/measure-perf` with 10 flows; need an analogous OPDS harness with at minimum: v1 root, v1 deep, v1 acquisition (single-comic), v2 root, v2 deep, v2 manifest single-comic, v2 progression GET, v2 progression PUT. Without this, every Tier 1-2 item is opinion-driven. | 00 (meta) | ✅ Stage 0 (`tests/perf/run_opds_baseline.py` + `baseline.json`) |
| R3  | **Per-route hit distribution.** Determines whether to prioritize start-page caching (#1 + #4) or feed-deep caching. If 80% of OPDS traffic is start-page or shallow folder-root, caching the start path alone captures most of the win without solving the general case. | 01 #1 | ⏳ Open |

---

## 3. Suggested landing order

Mirrors the browser-views phasing: measure first, then land
independent low-risk wins, then tackle structural items.

### Phase A — "measure before you cut" (required prep)

- [ ] Build the OPDS perf harness (R2 above). Mirror the structure of
      `tasks/browser-views-perf/measure-perf/` — JSON-output flows
      that record cold + warm timings + query count.
- [ ] Investigate `OPDS_TIMEOUT = 0` (R1). Run `git log -p
      codex/urls/const.py`, search the codex repo issues for
      "OPDS cache" / "OPDS timeout", and confirm what auth-key
      composition the feed routes use today.
- [ ] Record baseline timings for: v1 start, v1 deep folder, v1
      acquisition single-comic, v2 start, v2 deep folder, v2
      manifest, v2 progression GET, v2 progression PUT.

Without baselines + the disable rationale, Tier 1 #1 is blocked.

### Phase B — high-value, low-risk OPDS-specific wins

Independent fixes that don't depend on Tier 1 #1 landing:

- **#3** (story_arc N+1 fix) — single-line change.
- **#6** (`is_allowed` static → instance method) — small, mechanical.
- **#12** (`_update_feed_modified` use existing mtime) — cleanup.
- **#13** (extract `_obj_ts` helper) — refactor.
- **#15** (remove dead expression) — cleanup.

Together: a handful of small PRs over 1-2 days. Verify with the
Phase A harness.

### Phase C — manifest batching (Tier 1 #2 + Tier 2 #5)

Manifest is hit per-comic when readers open publications. The
credit fan-out (#2) and M2M subject loop (#5) are the two biggest
single wins inside the manifest endpoint. Land #2 first
(11 queries → 1) since the structural shape is simpler, then #5
(7 queries → 1). Together they drop manifest cold-query count by
~17 queries.

Before starting, **close R3 (serializer audit equivalent for OPDS)** —
the manifest may have lazy serializer fields not yet identified.

### Phase D — caching (Tier 1 #1) + start-page batching (Tier 1 #4)

This is the biggest-impact phase but also the highest-risk:

1. Confirm R1 (the `OPDS_TIMEOUT = 0` rationale) is resolved.
2. Set `OPDS_TIMEOUT = 60`, add `vary_on_headers("Cookie",
   "Authorization")` if not already present on feed routes.
3. Verify with the Phase A harness that response correctness holds
   across users (no cross-user leakage, fresh content after
   library updates).
4. Land #4 (preview-pipeline re-runs) as a follow-on. Once #1 is in
   place, the preview pipeline runs at most once per cache-window,
   so the per-spec re-run cost is amortized; #4 is still worth doing
   because cold paths are still the cold paths.

### Phase E — progression and v1 acquisition (Tier 2 #7, #8)

Smaller volume than feeds, but worth tightening:

- #7 (v1 entry M2M batch) — only worth doing if traffic data shows
  multi-book acquisition feeds are common.
- #8 (progression PUT conditional update) — independent, mechanical.

### Phase F — clean-ups (Tier 3 + 4)

Land in any order. Each is a small, isolated PR.

---

## 4. Cross-cutting guidance

A few patterns surfaced in multiple sub-plans; addressing them at
the architectural level prevents recurrence.

### A. Static method `is_allowed` is the wrong shape

`v2/feed/publications.py:35-56` is `@staticmethod` so it doesn't
have access to `self.admin_flags`. The result is an uncached
`AdminFlag.objects.get(...)` query inside what should be a hot
loop. The same shape exists at `v1/facets.py:158-164`.

**Rule for future code:** any check that reads an `AdminFlag` must
go through `self.admin_flags`, which is the request-scoped
`MappingProxyType` populated by
`codex/views/browser/filters/search/parse.py:197-211`. Never query
`AdminFlag` directly in a view body.

### B. Comicbox should not open on the request thread

`v1/entry/links.py:120-128` opens a comic file (CBZ/CBR/PDF) on
the serializer hot path when metadata is missing. The async
re-import already queued covers the correctness case; the
synchronous open is just there for the immediate response.

**Rule for future code:** disk I/O on a comic file belongs in the
librarian daemon, not in a view. The view's job is to render what
the indexer already produced. Use sentinel values (0 page count,
unknown file type) and let the next request after re-import
render correctly.

### C. Per-row FK access via `.only(...)` is an anti-pattern

`v2/manifest.py:122-144` uses `.only("story_arc", "number")` and
then accesses `.story_arc.name` per row. This is a textbook N+1.

**Rule for future code:** when a queryset's row attributes will
be accessed in a Python loop, use `select_related` or `.values()`,
not `.only()` plus FK access. `.only()` defers FK columns; `.values()`
or `.select_related()` materializes them.

### D. Cachalot-unfriendly write paths

Same as browser plan §4C. Two OPDS instances:

- `OPDS2ProgressionView.put` — frequent write on read path.
- Any future bookmark-write code path triggered by OPDS feeds.

Tag any future code that writes on a read path with a comment
noting the cachalot impact, and consider adding a test that
asserts no writes during a plain GET.

### E. URL template cache

The v1 OPDS surface fires `reverse()` 5+ times per entry × 50
entries per page. The URL set is small and static; resolved
templates can be cached at module level. Same pattern useful in
the v2 manifest reading_order loop.

---

## 5. What this plan does NOT address

Out of scope for this pass:

- Views outside `codex/views/opds/` (browser, reader, admin, auth,
  etc.).
- Serializer-layer N+1 audit. The browser plan deferred its
  serializer audit to a separate handoff
  (`tasks/browser-views-perf/stage5e-handoff-serializer-audit.md`).
  When that audit lands, repeat for OPDS serializers in
  `codex/serializers/opds/`.
- Frontend OPDS clients.
- Authentication caching (relevant to #6 in sub-plan 06 — OPDS
  binary endpoints re-validate Basic auth on every request, which
  is unavoidable in the current DRF setup).
- Schema changes (denormalization, new indexes, PRAGMA tuning).
- Librarian / scribe perf.

---

## 6. Quick-reference: hotspot → sub-plan index

| Code location                                                     | Hotspot                                       | Sub-plan |
| ----------------------------------------------------------------- | --------------------------------------------- | -------- |
| `codex/urls/const.py:7`                                           | `OPDS_TIMEOUT = 0`                            | 01 #1    |
| `codex/urls/opds/binary.py:34-50`                                 | Cover route caching (already correct)         | 01 #2    |
| `codex/urls/opds/binary.py:23`                                    | Page route `cache_control` only               | 01 #3    |
| `codex/views/opds/feed.py:12-15`                                  | OPDS throttling                               | 01 #5    |
| `codex/views/opds/start.py:13-14`                                 | Start-page settings reset                     | 01 #6    |
| `codex/views/opds/v2/feed/__init__.py:35-55`                      | `_subtitle_filters` JSON re-parse             | 02 #5    |
| `codex/views/opds/v2/feed/__init__.py:193-204`                    | `_update_feed_modified` nested-loop rescan    | 02 #1    |
| `codex/views/opds/v1/facets.py:158-164`                           | Uncached AdminFlag in facet loop              | 02 #6    |
| `codex/views/opds/v1/facets.py:64`                                | v1 books `select_related`                     | 02 #3    |
| `codex/views/opds/v1/entry/entry.py:131-152`                      | Per-entry M2M fan-out (acquisition feeds)     | 03 #1    |
| `codex/views/opds/v1/entry/links.py:120-128, 140`                 | `lazy_metadata` Comicbox open                 | 03 #2    |
| `codex/views/opds/v1/entry/links.py:42, 56, 88, 116, 136`         | Per-entry `reverse()` calls                   | 03 #3    |
| `codex/views/opds/v1/entry/entry.py:118-129`                      | `_add_url_to_obj` model mutation              | 03 #4    |
| `codex/views/opds/v2/feed/publications.py:35-56`                  | Static `is_allowed` AdminFlag query           | 04 #2    |
| `codex/views/opds/v2/feed/publications.py:240-269`                | `get_publications_preview` pipeline re-runs   | 02 #2, 04 #3 |
| `codex/views/opds/v2/feed/publications.py:145`                    | `floor(datetime.timestamp(obj.updated_at))`   | 04 #4    |
| `codex/views/opds/v2/manifest.py:194-199`                         | Credit fan-out (11 queries / manifest)        | 05 #1    |
| `codex/views/opds/v2/manifest.py:122-144`                         | `story_arcs` N+1 via `.only(...)`             | 05 #2    |
| `codex/views/opds/v2/manifest.py:176-184`                         | `_publication_subject` 7-query loop           | 05 #3    |
| `codex/views/opds/v2/manifest.py:231-259`                         | `reading_order` per-page `reverse()`          | 05 #4    |
| `codex/views/opds/v2/manifest.py:101, 117, 137, 240, 265`         | Duplicate timestamp expressions               | 05 #6    |
| `codex/views/opds/v2/manifest.py:109-120`                         | `parent_folder` FK access (verify)            | 05 #8    |
| `codex/views/opds/v2/progression.py:200-229`                      | Progression PUT conflict pre-check + write    | 06 #1    |
| `codex/views/opds/v2/progression.py:226`                          | Dead expression                               | 06 #1    |
| `codex/views/opds/v2/progression.py:135-156`                      | Progression GET ACL filter                    | 06 #2    |
| `codex/views/opds/binary.py`                                      | Inherited from browser cover/page/download    | 06 #4    |
| `codex/views/opds/auth.py`                                        | Per-request Basic-auth validation             | 06 #6    |
