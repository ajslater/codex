# Stage 5 — Tier 3-4 cleanups

Closes Phase F from
[99-summary.md §3](99-summary.md#3-suggested-landing-order). Three
cleanup items land; two are intentionally skipped after audit.

## Headline

`v2_manifest`: **23 → 22 cold queries** (-1 parent_folder N+1).
Plus invisible-in-this-baseline structural wins for high-page-count
PDF manifests (~N reverse() calls saved per request) and filtered
feeds (one fewer JSON parse + URL-unquote per request).

| Flow            | Cold queries (before → after) | Notes                          |
| --------------- | ----------------------------: | ------------------------------ |
| **v2_manifest** |                  **23 → 22** | -1 parent_folder lazy FK       |
| (other 10)      |             within ±0 noise  |                                |

Artifacts:

- `tasks/opds-views-perf/stage5-before.json` — captured against
  post-Stage-4 HEAD.
- `tasks/opds-views-perf/stage5-after.json` — captured with the
  three cleanups applied.

## What landed

### #16 — `select_related("parent_folder")` on manifest queryset

`codex/views/opds/v2/manifest.py:OPDS2ManifestView.get_object`. The
manifest's `_publication_belongs_to_folder` reads
`obj.parent_folder.path` whenever `folder_view` is on. Without the
join, every manifest hit fired one lazy `Folder.objects.get` per
request — a textbook N+1 with N=1 (sub-plan 05 #8).

Adding the join scopes the cost to the manifest path only — feeds
don't access `parent_folder` so the JOIN isn't carried where it
doesn't pay off. Manifest cold drops from 23 → 22 queries on the dev
DB; silk SQL trace confirms the `codex_folder` query is gone.

### #11 — Memoize filters JSON parse via `self.params`

`codex/views/opds/v2/feed/__init__.py:_subtitle_filters`. The prior
implementation re-parsed `request.GET["filters"]` JSON inline:

```python
if not (
    (filters := qps.get("filters"))
    and (filters := urllib.parse.unquote(filters))
    and (filters := json.loads(filters))
):
    return parts
```

That's `urllib.parse.unquote` + `json.loads` of a JSON payload that
the BrowserView pipeline already parsed via
`BrowserSettingsFilterInputSerializer` at request validation time
(`self.params["filters"]` is the parsed dict). Reading from
`self.params` avoids the third parse:

```python
filters = self.params.get("filters") or {}
if not filters:
    return parts
```

Sub-millisecond per request, but on a hot client refresh path it
adds up. Plus removes the only `json` / `urllib.parse` import in
`_subtitle_filters`.

### #10 — Resolve `opds:bin:page` URL once for `_publication_reading_order`

`codex/views/opds/v2/manifest.py:_publication_reading_order`. The
prior loop fired `self.href()` per page (which calls `reverse()`,
camelcases query params, and optionally builds an absolute URI) for
every page in `range(obj.page_count)`. For a 233-page comic that's
233 `reverse()` calls per manifest hit; for a PDF with 500+ pages,
500+ calls.

Replaced with a one-time URL resolution against a sentinel page
index, then `str.format` substitution per iteration:

```python
sentinel = _READING_ORDER_PAGE_SENTINEL  # 999_999_999
sentinel_href = self.href(HrefData(
    {"pk": obj.pk, "page": sentinel},
    {"ts": ts},
    url_name="opds:bin:page",
    min_page=0,
    max_page=sentinel,
))
template = sentinel_href.replace(f"/{sentinel}/", "/{page}/")
return [
    {"href": template.format(page=p), "type": MimeType.JPEG}
    for p in range(obj.page_count)
]
```

The sentinel is wider than any plausible page count; widening
`max_page` accordingly satisfies `_href_page_validate`. The
`/<sentinel>/` segment is unique within the resolved URL (the
`opds:bin:page` URL pattern is `c/<int:pk>/<int:page>/page.jpg`), so
the `replace` is unambiguous.

The harness's `v2_manifest` flow uses a 1-page comic; for that
comic the win is invisible (1 reverse() call either way). Sampled a
233-page comic separately: cold manifest 67-79ms (was 80-90ms with
the loop). On a 500+ page PDF the saving scales linearly.

## What was audited and intentionally skipped

### #12 — `_update_feed_modified` rescan

The plan's claim that `_get_group_and_books`'s mtime supersedes the
rescan turned out to be wrong on read of the data flow:

- `OPDS2StartView._update_feed_modified` walks `groups` looking at
  each preview group's `publications[*].metadata.modified`.
- Preview groups are produced by `get_publications_preview` which
  builds a fresh `OPDS2FeedLinksView()` per `PREVIEW_GROUPS` link
  spec. Each preview's mtime comes from the previewed publications,
  NOT from the parent view's `_get_group_and_books` mtime.
- Removing the rescan would lose preview-group mtime tracking and
  produce a stale feed `modified` header on the start page.

The "duplicate timestamp computation" the plan flagged was a
misread; the rescan is the only path that aggregates preview-group
mtimes back up to the start-page metadata. Wall time of the
Python-side scan is ~10µs on the dev DB (3 preview groups × ≤5
publications). Not worth a structural refactor. Closing as
won't-fix.

### #18 — `_add_url_to_obj` mutation pattern

The plan flagged this as "code health, not perf" — `_add_url_to_obj`
mutates queryset-row model instances to attach a `.url` attribute,
which is "fragile" because cachalot can in principle reuse model
instances.

Stage 4's batched paths already produce `SimpleNamespace(pk, name,
url)` objects via the new `get_credit_people_by_comic` helper —
never touch DB instances. The legacy `_add_url_to_obj` only fires
on the per-entry single-comic fallback (facet entries / single-comic
acquisition feeds) where:

1. The comic is loaded fresh per request (no cachalot reuse risk).
2. The materialized `result.append(obj)` returns a list, not a
   queryset, so mutated instances don't propagate back to cachalot.

Making the fallback path use `SimpleNamespace` for parity is
mechanical but adds churn for negligible benefit. Closing as
won't-fix; Stage 4's batched path already exemplifies the cleaner
pattern for any future code.

## Verification

- **`make test`** — 24 / 24 pass.
- **`make lint`** — Python lint passes; pre-existing remark warning
  on plan markdown unchanged.
- **Manifest spot-check** on 233-page comic: 233 `readingOrder`
  entries, hrefs match `…/c/157/<page>/page.jpg?ts=…` for page 0
  through 232. URL templating produces correct output.
- **Filtered feed spot-check**: filtered feeds still render correct
  subtitle parts.
- **Folder-gated manifest**: silk trace confirms `codex_folder`
  query is gone post-fix.

## Plan status

After Stage 5, the OPDS perf plan is largely closed:

| Tier | Items closed | Items still open |
| ---- | ------------ | ---------------- |
| 1    | #1, #2, #3, #4 | — |
| 2    | #5, #6, #7, #8 | — |
| 3    | #10, #11      | #9 (defer Comicbox open), #12 (audited won't-fix) |
| 4    | #13, #15, #16, #17 | #14 (URL template cache), #18 (audited won't-fix), #19 (cachalot tagging) |
| R    | R1, R2 | R3 (per-route hit distribution; needs prod telemetry) |

Remaining open items are either (a) medium-risk and need correctness
verification (#9), (b) need traffic data (#19, R3), or (c) trivial
incremental wins where the framework cost dwarfs the optimization
target (#14 URL template cache — Django's `reverse()` is fast enough
in profile).

The OPDS perf project has reached the point where additional wins
need either external signal (production traces, real-user telemetry)
or accept higher correctness risk. Recommend pausing
[`tasks/opds-views-perf/`](.) here and reopening once production
data shows specific paths to optimize.
