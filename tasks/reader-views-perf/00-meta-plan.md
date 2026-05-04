# Codex `codex/views/reader/` — Performance Plan: Methodology

How this analysis is organized. Mirrors the structure of the
[`tasks/opds-views-perf/`](../opds-views-perf/) plan; the goal is to
produce a comparable ranked backlog for the reader subsystem.

## Scope

Everything under `codex/views/reader/` (6 source files,
~850 LOC), plus the URL configuration in `codex/urls/api/reader.py`.
The cover endpoint mounted under that URL conf
(`<pk>/cover.webp`) routes to `codex.views.browser.cover.CoverView`
and was already optimized in the browser-views perf project; not
re-analyzed here.

Out of scope (matches OPDS plan):

- Browser views, OPDS views, admin views, librarian daemon.
- Frontend (`/frontend/` — reader UI).
- Comicbox internals, archive parsing, page extraction.
- Schema changes (denormalization, indexes, PRAGMA tuning).

## Why now

The browser-views perf project (Stage 0 → 5e) closed the bulk of the
ACL / annotation / FTS hotspots. The OPDS perf project (Stages 0
through 5) closed the OPDS-specific batching + caching wins. The
reader is the last large feature view family that hasn't been
audited for performance.

Reader matters because the user's comic-reading hot path goes
through it:

1. User clicks a comic in the browser → `c/<pk>` (`ReaderView`) is
   hit. Returns the comic + the prev/curr/next book window + the
   arc context + reader settings.
2. User reads → `c/<pk>/<page>/page.jpg` (`ReaderPageView`) is hit
   per page turn. The hottest endpoint in the codex.
3. User changes per-comic settings → `c/<pk>/settings`
   (`ReaderSettingsView`) is hit on every adjustment.

Latency on (1) is felt as "click-to-open"; latency on (2) is felt
as "page-turn lag." Both deserve scrutiny.

## Surface map

| File | LOC | Class | Role |
| ---- | --- | ----- | ---- |
| `params.py` | 70 | `ReaderParamsView` | Base class — input validation + memoized params dict + arc kwarg shape. |
| `arcs.py` | 134 | `ReaderArcsView` | Build the arc context (series / volume / folder / story_arc list for the comic). |
| `books.py` | 181 | `ReaderBooksView` | Build the prev / current / next book window inside the selected arc. |
| `reader.py` | 49 | `ReaderView` | Top-level view — assembles arcs + books + close_route into the `c/<pk>` GET response. |
| `page.py` | 106 | `ReaderPageView` | Streams the page image bytes for `c/<pk>/<page>/page.jpg`. |
| `settings.py` | 309 | `ReaderSettingsBaseView`, `ReaderSettingsView` | Per-scope (global / comic / series / folder / story_arc) settings CRUD. |
| __init__.py | 1 | — | — |

Inheritance chain for the main view:

```
SettingsBaseView
└── ReaderSettingsBaseView (settings.py)
    └── ReaderParamsView (params.py)
        └── ReaderArcsView (arcs.py)
            └── ReaderBooksView (books.py) + SharedAnnotationsMixin + BookmarkAuthMixin
                └── ReaderView (reader.py)
```

Side branches:

- `ReaderSettingsView(ReaderSettingsBaseView)` — settings CRUD endpoint.
- `ReaderPageView(BookmarkAuthMixin, AuthFilterAPIView)` — page binary.

URL routes (`codex/urls/api/reader.py`):

| Route | View | Cache |
| ----- | ---- | ----- |
| `c/<pk>` | `ReaderView` | **none** |
| `c/<pk>/<page>/page.jpg` | `ReaderPageView` | `cache_control` only (HTTP cache headers; no server-side `cache_page`) |
| `c/<pk>/cover.webp` | `CoverView` (browser) | `cache_page(COVER_MAX_AGE)` + `vary_on_cookie` (already optimal) |
| `c/settings` and `c/<pk>/settings` | `ReaderSettingsView` | none |
| `c/<pk>/download/<filename>` | `DownloadView` (browser) | none — download is single-shot |

The reader and settings endpoints are uncached server-side. Page is
client-cache only.

## Plan structure

Three sub-plans plus the summary:

- [`01-reader-view-chain.md`](01-reader-view-chain.md) — `ReaderView`
  + the params/arcs/books inheritance chain. The main reader request
  (`c/<pk>`).
- [`02-reader-settings.md`](02-reader-settings.md) — settings CRUD
  (`c/settings`, `c/<pk>/settings`).
- [`03-reader-page.md`](03-reader-page.md) — page binary
  (`c/<pk>/<page>/page.jpg`).
- [`99-summary.md`](99-summary.md) — ranked backlog with severity,
  effort, risk, and a suggested landing order.

The reader surface is small enough that this 3-plan + summary shape
is adequate. The OPDS plan's 6-sub-plan decomposition would be
over-engineered here.

## Methodology (mirrors OPDS / browser plans)

For each view family the analysis answers four questions:

1. **What's the per-request cost shape?** — Lines fired in the hot
   path: SQL queries, Comicbox opens, `reverse()` calls,
   serialization passes.
2. **What's the per-row / per-page fan-out?** — Where the cost
   scales with N. (Pre-fix OPDS had `9 × N entries` for v1
   acquisition feeds; the reader has analogous patterns.)
3. **What's batchable / cacheable?** — Whether the cost is fixed
   per-request or amortizable across a tab refresh / page sequence.
4. **What's the risk profile of fixing it?** — Pure refactor (low),
   query reshape (medium), behavior change (high).

Where possible, link sub-plan items into a single ranked backlog in
[`99-summary.md`](99-summary.md). Status starts ⏳ Open until items
land; mirrors the OPDS plan's status column convention.

## What this plan does NOT address

Same posture as the OPDS plan:

- Serializer-layer audit. `codex/serializers/reader.py` has its own
  N+1 risks worth checking, but the audit belongs to a separate
  serializer-perf handoff (mirror of
  `tasks/browser-views-perf/stage5e-handoff-serializer-audit.md`).
- Reader UI / frontend.
- Schema changes.
- Comicbox internals — page extraction, archive parsing, PDF
  rendering.
- Librarian / scribe perf.

## What's worth measuring before scheduling

1. **Reader endpoint cold latency.** Single hit on `c/<pk>` —
   how many SQL queries, how much wall time.
2. **Page endpoint cold latency.** Single hit on
   `c/<pk>/<page>/page.jpg` — how much of the wall time is
   Comicbox vs. ACL filter.
3. **Per-route hit distribution.** Reader endpoint volume vs. page
   endpoint volume. Page is the hotter endpoint per session
   (page turn count vs. comic open count); confirm with traffic
   data before prioritizing.
4. **Settings endpoint volume.** Settings are written on UI
   adjustments; if low-volume, the get-or-create pattern doesn't
   matter even if it's two queries.

Build a reader perf harness analogous to
`tests/perf/run_opds_baseline.py` covering at minimum: reader
endpoint cold, page endpoint cold, settings GET multi-scope, page
turn warm. Without baselines, the rankings in
[`99-summary.md`](99-summary.md) are opinion-driven.
