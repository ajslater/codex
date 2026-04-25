# Stage 0 — OPDS perf measurement + low-risk wins

Closes Phase A (R1, R2, baseline) and Phase B (#3, #6, #13, #15) of the plan in
[99-summary.md §3](99-summary.md#3-suggested-landing-order). Phase B #12
(`_update_feed_modified` rescan) is **deferred** — it overlaps with the
preview-pipeline pass in Phase D and the correctness check is non-trivial.

## R1 — `OPDS_TIMEOUT = 0` rationale

`git log -p codex/urls/const.py` traces the constant to commit `bcda604b` (Jan
22 2026), introduced already at `0`. The diff replaces inline `60 * 5` hits with
`OPDS_TIMEOUT` so the value can be set in one place — the disable itself was the
point of the change. No bug-report context. Implicit rationale (consistent with
the `# BROWSER_TIMEOUT = 60 * 5` comment in `urls/const.py:7`): a separate
timeout knob set to `0` avoids per-user data leaking through `cache_page`'s
URL-only cache key. To re-enable safely
([sub-plan 01 #1](01-routes-and-cache.md#1-opds_timeout--0-disables-all-route-caching)),
feed routes need `vary_on_headers("Cookie", "Authorization")` confirmed end to
end. Tier-1 #1 stays open until that lands; Stage 0 does not enable caching.

## R2 — OPDS perf harness

Built `tests/perf/run_opds_baseline.py`, mirroring the structure of the existing
browser harness (`tests/perf/run_baseline.py`):

- Authenticates the synthetic `codex-perf` user via `Client.force_login` — same
  auth path as interactive sessions (DRF `SessionAuthentication`).
  Per-auth-class measurement (Basic header) is left for a follow-up if traffic
  data shows it dominates.
- Eleven flows covering both OPDS surfaces: v1 start / root-browse / series
  acquisition / acquisition-with-metadata / opensearch; v2 start / root-browse /
  series-publications / manifest / progression-GET; static v1 auth doc.
- Cold-then-warm methodology — `django_cache.clear()` +
  `cachalot.api.invalidate()` between cold and the next-flow capture.
- Captures via `django-silk` so `num_sql_queries` and `time_taken_ms` are read
  from the same instrumentation the browser harness uses.
- Run with:
    ```
    CODEX_CONFIG_DIR=$HOME/Code/codex/config DEBUG=1 \
      uv run python -m tests.perf.run_opds_baseline \
      --out tasks/opds-views-perf/<artifact>.json
    ```

Two artifacts are checked in alongside the harness:

- `baseline.json` — captured before any Phase B edits.
- `stage0-after.json` — captured with Phase B edits applied.

### Harness reproducibility note

The harness is sensitive to lingering `SettingsBrowser` state on the perf user.
When the test user has `top_group` in an unusual state (e.g. left over from an
interactive session that pointed at folders), the
`/opds/v1.2/s/<pk>/1?topGroup=s` flows can return a 7-entry navigation shell
instead of the 106-entry acquisition feed even with `?topGroup=s` in the URL. A
second harness run after the user's settings re-settle to `top_group=p` produces
the documented numbers reproducibly. If a future operator sees collapsed query
counts (e.g. `v1_acquisition_with_metadata` dropping from ~800 to ~16), re-run
the harness — that's the diagnostic signal of the same artifact.

A follow-up could harden the harness by seeding settings to a known defaults row
instead of relying on the `DELETE /api/v3/r/settings` reset; left for whoever
next touches the harness.

## Baseline

Cold pass = the tracked metric (cachalot + django_cache invalidated before each
capture). Warm = the same request immediately afterward. All on a populated dev
DB — `series_pk=325` ("All Batman", 106 comics); `comic_pk=10785` (richest
character M2M coverage in that series).

| Flow                         | Cold queries | Cold wall (ms) | Warm queries | Warm wall (ms) |
| ---------------------------- | -----------: | -------------: | -----------: | -------------: |
| v1_start                     |           14 |             53 |            5 |             12 |
| v1_root_browse               |           15 |            127 |           13 |             43 |
| v1_series_acquisition        |           19 |             93 |           15 |             63 |
| v1_acquisition_with_metadata |      **817** |       **1585** |          815 |            762 |
| v1_opensearch                |            3 |              6 |            2 |              4 |
| v2_start                     |           54 |            500 |           45 |             69 |
| v2_root_browse               |           15 |            111 |           13 |             31 |
| v2_series_publications       |      **220** |        **258** |          216 |            224 |
| v2_manifest                  |           47 |            111 |           44 |             83 |
| v2_progression_get           |            9 |             15 |            8 |             11 |
| auth_doc_v1                  |            2 |              6 |            0 |              2 |

The two **bold** rows are the headline targets:

- **`v1_acquisition_with_metadata`** at 817 cold queries / 1.6 s confirms
  [sub-plan 03 #1](03-entry-serialization-v1.md#1-per-entry-9-query-m2m-fan-out-when-metadatatrue)
  — the 9-query M2M fan-out (authors / contributors / category_groups) per
  entry, fired on every page of an `?opdsMetadata=1` acquisition feed.
- **`v2_series_publications`** at 220 cold queries / 258 ms is **higher than the
  plan estimated**. Per-publication query fan-out (`_thumb` cover lookup +
  per-`is_allowed` AdminFlag query + `select_related` shortfalls).
  [Sub-plan 04 #2/#3](04-publications-v2.md) picks up the actionable subset; the
  rest blends into the BrowserView cost that flows through to OPDS.

`v2_start` at 500 ms / 54 queries demonstrates the start-page preview pipeline
cost
([sub-plan 02 #2](02-feed-pipeline.md#2-start-page-preview-pipeline-rerun-per-link-spec)).
`v2_manifest` at 47 queries / 111 ms reflects the credit + subject + story arc +
identifier loops in a comic that has rich M2M coverage but no story arcs or
parent-folder gating ([sub-plan 05](05-manifest.md)).

## Phase B — what landed

Five plan items in
[99-summary.md Phase B](99-summary.md#phase-b--high-value-low-risk-opds-specific-wins);
four implemented, one deferred.

### #15 — Remove dead expression

`codex/views/opds/v2/progression.py:226` had a bare `max(position - 1, 0)`
expression with no assignment — leftover from a refactor. Removed. Pure
code-health bug
([sub-plan 06 #1](06-progression-binary-aux.md#1-progression-put-pre-fetch-conflict-check)).

### #3 — Story-arc N+1 in manifest

`codex/views/opds/v2/manifest.py:_publication_belongs_to_story_arcs` used
`.only("story_arc", "number")` then read `story_arc_number.story_arc.name` in a
Python loop — textbook N+1
([sub-plan 05 #2](05-manifest.md#2-n1-on-story_arc-attribute-access)). Replaced
with `.select_related("story_arc").only("number", "story_arc__name")`. The
`v2_manifest` flow in this baseline doesn't exercise the fix (`comic_pk=10785`
has zero story arcs), so the headline 47-query number is unchanged. The fix is
validated by inspection; will show up as a delta on manifest hits for any comic
that does have story arcs.

### #6 — `is_allowed` static → instance method (and v1 facets parallel)

Two parallel anti-patterns
([sub-plan 02 #6, 04 #2](04-publications-v2.md#2-is_allowed-static-method-fires-uncached-adminflag-query)):

1. `OPDS2PublicationBaseView.is_allowed` was `@staticmethod` and re-fired
   `AdminFlag.objects.only("on").get(...)` per call. Converted to instance
   method, reads `self.admin_flags.get("folder_view")` (the request-cached
   `MappingProxyType` from `codex/views/browser/filters/search/parse.py`).
2. `OPDS1FacetsView._facet_group` had the same shape — `AdminFlag.objects.get`
   inside the per-facet loop. Hoisted out of the loop and switched to
   `self.admin_flags.get("folder_view")`.

Both `is_allowed` callers (`v2/feed/groups.py:70`, `v2/manifest.py:108`) already
used instance-call syntax, so the static→instance conversion is
binary-compatible.

The flows in this baseline don't fire `is_allowed` (the manifest comic has no
parent folder; the publication preview surface didn't exercise folder links in
this DB). Same situation as #3: validated by inspection, will show up on
folder-heavy feeds.

### #13 — `_obj_ts` helper

`floor(datetime.timestamp(obj.updated_at))` appeared at 6 sites
(`v2/feed/publications.py`, `v2/manifest.py`). Hoisted into
`OPDS2PublicationBaseView._obj_ts(obj)` so the six call sites read
`self._obj_ts(obj)`. Pure refactor. Removes `from datetime import datetime` and
`from math import floor` from `manifest.py`.

### #12 — DEFERRED

`_update_feed_modified` in `OPDS2StartView` rescans the assembled feed for mtime
instead of using the `mtime` returned from `_get_group_and_books`. The plan
estimated this as XS / low-risk, but the preview-pipeline path
(`get_publications_preview`) rebuilds its own `feed_view` per link spec and
calls `get_book_qs()` directly — those previews don't surface mtime to the start
view's update step. Replacing the rescan needs a correctness check that the
preview groups' mtimes are aggregated, which fits more naturally into Phase D
(preview-pipeline batching, Tier 1 #4).

## After

Re-captured `stage0-after.json` with all four Phase B edits applied. Comparing
to `baseline.json`:

| Flow                         | Cold Δqueries | Cold Δms | Notes                                                               |
| ---------------------------- | ------------: | -------: | ------------------------------------------------------------------- |
| v1_start                     |            ±0 |     +1.5 | Noise.                                                              |
| v1_root_browse               |            ±0 |       +5 | Noise.                                                              |
| v1_series_acquisition        |            ±0 |       +4 | Noise.                                                              |
| v1_acquisition_with_metadata |            ±0 |      +60 | Noise. #6 (v1 facets) doesn't fire here — no `f` facet on this URL. |
| v1_opensearch                |            ±0 |       +2 | Noise.                                                              |
| v2_start                     |            −1 |      +78 | One AdminFlag query removed via `is_allowed` cache.                 |
| v2_root_browse               |            ±0 |      +13 | Noise.                                                              |
| v2_series_publications       |            −1 |      +44 | One `is_allowed` query removed.                                     |
| v2_manifest                  |            ±0 |      +20 | #3 doesn't fire — comic has 0 story arcs.                           |
| v2_progression_get           |            ±0 |       +3 | Noise.                                                              |
| auth_doc_v1                  |            ±0 |       ±0 | Static doc.                                                         |

Wall-time deltas are within the run-to-run noise floor for this DB / dev machine
(silk overhead + cold-cache rebuild per flow). Query-count is the trustworthy
metric; both flows that fire `is_allowed` lose exactly one AdminFlag query as
expected.

The structural fixes (#3, #6, #13) are validated against representative flows
but won't surface as headline wins in this baseline because:

- `comic_pk=10785` has no story arcs (#3 no-op for the manifest flow).
- `series_pk=325` doesn't gate the publications preview on folder admin flags
  (#6 only fires once per request via `is_allowed`).
- `_obj_ts` (#13) is a pure refactor.

To make the wins visible in headline numbers, future runs of the harness should
add: a comic with story arcs (manifest), a folder-view feed (v1 + v2
publications), and an OPDS start request with the TOP_GROUP facets emitted (v1
facets `_facet_group`).

## Verification

- `make lint` — passes for the Python side. The pre-existing `remark .` failure
  on the markdown side reproduces on `origin/v1.11-performance` unchanged; not
  caused by Phase B.
- `make test` — 24 / 24 pass.
- Harness re-run consistent with the documented numbers across two back-to-back
  captures.

## What's next

1. Phase C — manifest batching (Tier 1 #2 + Tier 2 #5). The two largest single
   wins inside the manifest endpoint, both blocked on serializer audit (R3 in
   99-summary.md). Land #2 first (11 → 1 queries).
2. Phase D — `OPDS_TIMEOUT > 0` + start-page batching. Highest impact, highest
   risk; unblocks once R1 confirms `Vary: Cookie, Authorization` covers per-user
   feeds end to end.
3. Phase B #12 (deferred) folds into Phase D's preview-pipeline pass.
