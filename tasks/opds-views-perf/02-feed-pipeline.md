# 02 — Feed pipeline (v1 + v2 main feed views)

How the v1 Atom feed and v2 JSON feed views orchestrate the
`BrowserView` pipeline and what work they layer on top.

## Files in scope

| File                                       | LOC | Purpose                                              |
| ------------------------------------------ | --- | ---------------------------------------------------- |
| `codex/views/opds/v1/feed.py`              | 178 | `OPDS1FeedView` + `OPDS1StartView`                   |
| `codex/views/opds/v1/links.py`             | 155 | Top-level navigation, pagination, facet links        |
| `codex/views/opds/v1/facets.py`            | 186 | Facet entries / nav links                            |
| `codex/views/opds/v2/feed/__init__.py`     | 212 | `OPDS2FeedView` + `OPDS2StartView`                   |
| `codex/views/opds/v2/feed/feed_links.py`   | 115 | Pagination + static feed links                       |
| `codex/views/opds/v2/feed/links.py`        | 146 | Link aggregation, self-link detection                |
| `codex/views/opds/v2/feed/groups.py`       | 174 | Group/facet assembly, preview group orchestration    |
| `codex/views/opds/v1/const.py`             | 196 | Data classes + facet enums (no DB cost)              |
| `codex/views/opds/v2/const.py`             | 172 | Data classes + facet enums (no DB cost)              |
| `codex/views/opds/v2/href.py`              | 65  | URL building with template expansion                 |
| `codex/views/opds/const.py`                | 116 | Shared constants                                     |

## Per-request flow

### v1 root browse, no filters

1. URL match → `OPDS1FeedView.get`.
2. `serializer.data` accessed → triggers `entries` property.
3. `entries` property (`v1/feed.py:139-158`):
    - `add_top_links(RootTopLinks.ALL)` (start page only) or
      `add_start_link()` (non-start).
    - `facets(entries=False)` — see 03 for cost.
    - `_get_entries_section("groups", metadata=False)` — iterates
      group queryset, instantiates `OPDS1Entry` per row.
    - `_get_entries_section("books", metadata)` — iterates book
      queryset, instantiates `OPDS1Entry` per row, calls
      `entry.lazy_metadata()` per book.
4. `links` property assembles top-level feed links.

### v2 root browse, no filters

1. URL match → `OPDS2FeedView.get`.
2. `get_object()` (`v2/feed/__init__.py:144-176`):
    - `self.group_and_books` — memoized `_get_group_and_books()` from
      BrowserView (one cascade of the full annotation pipeline).
    - `_feed_metadata(...)` — pure assembly.
    - `get_links(up_route)` — link list.
    - `_feed_navigation_and_groups(...)` — branches on start page.

The start-page branch calls `get_ordered_groups()` which fires
`get_publications_preview()` per `PREVIEW_GROUPS` link spec (see #2
below).

## Hotspots

### #1 — `OPDS2StartView._update_feed_modified` does a nested-loop scan after the feed is built

`v2/feed/__init__.py:193-204`:

```python
@override
@staticmethod
def _update_feed_modified(feed_metadata, groups):
    max_modified = EPOCH_START
    for group in groups:
        for publication in group.get("publications", []):
            modified = publication.get("metadata", {}).get("modified", EPOCH_START)
            max_modified = max(max_modified, modified)
    if max_modified != feed_metadata["modified"]:
        feed_metadata = dict(feed_metadata)
        feed_metadata["modified"] = max_modified
    return feed_metadata
```

Walks every group + every publication after the feed is fully
materialized to find the max `modified` timestamp. With 5 preview
groups × 5 publications each = 25 iterations on the start page —
small, but every nested dict access is a Python-level Hash lookup.

The same value is already computed by the BrowserView pipeline as
`mtime` (see `_get_group_and_books`'s return tuple, fifth element).
The start view could pull `mtime` from there instead of re-scanning
the assembled feed.

**Severity:** low individually, but cleanup-worthy. Removes
duplicate timestamp computation and the only reason the
`_feed_navigation_and_groups` method has to return its full nested
data structure pre-serialization.

### #2 — `get_publications_preview` re-runs the full filter pipeline per preview group

`v2/feed/groups.py:142-150` calls `get_publications_preview(link_spec)`
for each `link_spec` in each `PREVIEW_GROUPS` LinkGroup. Each call
chains into `v2/feed/publications.py:255-269`:

```python
def get_publications_preview(self, link_spec: Link) -> list:
    feed_view = self._get_publications_preview_feed_view(link_spec)
    book_qs, book_count, zero_pad = feed_view.get_book_qs()
    if not book_count:
        return []
    return self.get_publications(book_qs, ...)
```

`_get_publications_preview_feed_view` (lines 240-253) instantiates a
fresh `OPDS2FeedLinksView`, sets `request` and `kwargs` and `params`,
then calls `set_params`. The next `get_book_qs()` call runs the full
ACL + search + annotation pipeline against the new params.

For a start page with 5 preview link specs, that's **5 full
filter-pipeline runs per request**. Each run shares the underlying
DB row coverage (same library, same user) but has different
`params["show"]` / `params["limit"]` / filter values.

Mitigation options:

- **Batch.** Build a single annotated queryset over the union of
  preview filter sets, partition the result rows post-fetch by
  link_spec membership. Ugly but eliminates 4 of the 5 cold queries.
- **Memoize on the view instance.** The browser-views ACL + search
  results are already memoized by `_cached_visible_library_pks` and
  the search parse cache (`tasks/browser-views-perf/05-replan.md`
  Stage 1). Some of the cost is already absorbed; verify how much
  remains.
- **Reduce preview width.** The current preview list is 5 link
  specs; if any of them is rarely useful in practice, dropping it
  is the cheapest fix.

**Severity:** medium-high. Start page is the most-hit OPDS endpoint
on a typical client.

### #3 — `select_related("series", "volume", "language")` is set on books in v1, not v2

`v1/facets.py:64`:

```python
book_qs = book_qs.select_related("series", "volume", "language")
```

This is correct for v1 because the entry properties read
`obj.series_name`, `obj.volume`, `obj.language` per row.

The v2 publications view, however, doesn't add this `select_related`.
`v2/feed/publications.py:_publication_metadata` reads
`obj.publisher_name`, `obj.imprint_name`, `obj.language.name`,
`obj.reading_direction` per publication. Most of those are already
denormalized fields on `Comic` (no FK), but `obj.language` is an FK.
**Verify** whether `language` is already on the queryset (likely yes,
since it's annotated by browser-views) or if it's a per-row FK fetch.

**Severity:** low. Worth confirming with `django-debug-toolbar`
before scheduling. Inherited from browser-views annotation pipeline,
which already covers the common case.

### #4 — `OPDS2FeedLinksView` self-link detection iterates all links per request

`v2/feed/feed_links.py` (115 LOC) builds the link list and walks it
to find the `rel="self"` entry for OPDS clients that need it. With
~10 links per feed this is a sub-millisecond walk; flagged for
completeness only.

**Severity:** trivial.

### #5 — `_subtitle_filters` parses request.GET["filters"] JSON twice on a filtered v2 feed

`v2/feed/__init__.py:35-55`:

```python
if not (
    (filters := qps.get("filters"))
    and (filters := urllib.parse.unquote(filters))
    and (filters := json.loads(filters))
):
    return parts
```

The same JSON is parsed elsewhere in the BrowserView pipeline (filter
serializer at request-validation time and again in
`get_comic_field_filter`). Three parses per request on a filtered
feed. JSON is fast, but on a hot client refresh path it adds up.

**Mitigation:** cache the parsed filter dict on `self.params` early
in request lifecycle. The browser-views perf project's `params`
diff-save (Stage 1) is the obvious anchor — extend the same hook to
populate `self._parsed_filters` once.

**Severity:** low.

### #6 — v1 facet rendering may emit a per-facet AdminFlag query on folder-enabled installs

`v1/facets.py:158-164`:

```python
for facet in facet_group.facets:
    if facet.value == "f":
        efv_flag = (
            AdminFlag.objects.only("on")
            .get(key=AdminFlagChoices.FOLDER_VIEW.value)
            .on
        )
        if not efv_flag:
            continue
```

Inside a per-facet loop. For each facet group that contains a `"f"`
(folder) facet, this query fires once per check. The check is gated
on `facet.value == "f"` so it only fires per group. Still, **uncached
DB access inside a loop** — the kind of pattern the browser plan
flagged repeatedly.

A `cached_property` on the view (or a request-scoped scalar as
already exists for `admin_flags` in
`codex/views/browser/filters/search/parse.py:197-211`) would zero
this out. The `admin_flags` `MappingProxyType` already exposes
`folder_view`; this code should use it.

**Severity:** medium. See cross-cutting hotspot in 06.

### #7 — v1 facets and links re-walk top-link/facet-group enums per request

`v1/links.py:_links_facets` and `v1/facets.py:facets()` both iterate
`TopLinks.ALL` / `RootTopLinks.ALL` / `FacetGroups.*` enums on every
request. The enums are static (`v1/const.py`), so the work is pure
Python loop overhead. Not a real cost, but combined with the per-row
`reverse()` calls in entry links (sub-plan 03), the cumulative URL
build cost matters.

**Severity:** trivial individually; rolled into 03's URL build hotspot.

## Interactions with `BrowserView`

- `OPDS1FeedView` extends `OPDS1LinksView` extends `OPDS1FacetsView`
  extends `OPDSBrowserView` extends `BrowserView`. All
  pagination / annotation / filtering flows through `BrowserView`
  unchanged.
- `OPDS2FeedView` extends `OPDS2FeedGroupsView` extends
  `OPDS2PublicationsView` extends `OPDS2PublicationBaseView` extends
  `OPDS2FeedLinksView` extends `OPDS2LinksView` extends
  `OPDSBrowserView`. Deep chain, but each intermediate adds a single
  responsibility.
- Both feed views memoize `obj` / `group_and_books` on first access
  to avoid double-firing the BrowserView pipeline.

## Open questions

- **Are the preview-pipeline re-runs (#2) a real cost or absorbed by
  cachalot?** Each fresh view instance gets a different params
  dict, but the underlying queries hit the same row patterns —
  cachalot may already collapse them. Confirm with
  `django-debug-toolbar` before scheduling.
- **Does `_subtitle_filters` actually fire on every request, or only
  filtered ones?** Line 38 short-circuits on missing `filters` key —
  unfiltered requests should pay zero. Confirm.
