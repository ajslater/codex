# 04 — Publications (v2 JSON feed)

Per-publication serialization on the v2 JSON feed. Each book on the
page becomes one `dict` produced by `_publication(obj, zero_pad)`,
which builds metadata, links, and thumbnails. The hot loop sits in
`get_publications` (`v2/feed/publications.py:208-238`) and the per-
publication helpers live in the same module plus `v2/feed/groups.py`.

## Files in scope

| File                                       | LOC | Purpose                                              |
| ------------------------------------------ | --- | ---------------------------------------------------- |
| `codex/views/opds/v2/feed/publications.py` | 269 | `OPDS2PublicationBaseView` + `OPDS2PublicationsView` |
| `codex/views/opds/v2/feed/groups.py`       | 174 | Group/facet assembly, `get_ordered_groups`           |
| `codex/views/opds/v2/feed/feed_links.py`   | 115 | Pagination + static feed links                       |
| `codex/views/opds/v2/feed/links.py`        | 146 | Link aggregation, self-link detection                |

## Per-publication cost shape

Each call to `_publication(obj, zero_pad)`:

1. `_publication_metadata(obj, zero_pad)` — pure attribute reads from
   the queryset row plus `Comic.get_filename` or `Comic.get_title`.
2. Three `_publication_link(...)` calls — one each for download,
   progression, and manifest. Each builds an `HrefData` and a
   `LinkData` dict; `self.link(...)` resolves URL via `reverse()`.
3. `_thumb(obj)` — one more `reverse()` for the cover URL.

For a typical 50-publication page, that's roughly **4 reverse() per
publication** plus pure-Python dict construction. No DB queries on
the per-publication path itself (everything is from the row).

## Hotspots

### #1 — `_publication_metadata` invokes `self.admin_flags["folder_view"]` per publication

`v2/feed/publications.py:58-80`:

```python
def _publication_metadata(self, obj, zero_pad) -> dict:
    title_filename_fallback = bool(self.admin_flags.get("folder_view"))
    if self.kwargs.get("group") == "f":
        title = Comic.get_filename(obj)
    else:
        title = Comic.get_title(...)
```

`self.admin_flags` is the request-cached `MappingProxyType` from
`codex/views/browser/filters/search/parse.py:197-211`. It's already
memoized on first access — subsequent reads are dict lookups. **Not a
hotspot,** but worth noting because the parallel `is_allowed` static
method (#2) does **not** use this cache.

### #2 — `is_allowed` static method bypasses the request-cached `admin_flags`

`v2/feed/publications.py:35-56`:

```python
@staticmethod
def is_allowed(link_spec: Link | BrowserGroupModel) -> bool:
    if (...):
        # Folder perms
        efv_flag = (
            AdminFlag.objects.only("on")
            .get(key=AdminFlagChoices.FOLDER_VIEW.value)
            .on
        )
        if not efv_flag:
            return False
    return True
```

Called from:

- `v2/feed/groups.py:_create_links_from_link_spec` line 70 — once per
  link spec in `_create_links_from_link_spec`. Loops over LinkGroup
  links per top-level group (start page + facets).
- `v2/manifest.py:_publication_belongs_to_folder` line 110 — once per
  manifest request that has a folder.
- (search the codebase for other call sites; the static-method
  signature makes it easy to misuse.)

The query is `AdminFlag.objects.only("on").get(...)`. That hits the
DB once per call unless cachalot has it cached. Even with cachalot,
the call goes through the ORM layer — not free.

Mitigation:

- Convert `is_allowed` to an instance method and read
  `self.admin_flags["folder_view"]`. Single edit, eliminates the
  query path.
- For the manifest call (single comic, single check), the win is
  trivial. For the start-page facet/group rendering, the win
  multiplies by the number of folder-related link specs.

**Severity:** medium. Same uncached AdminFlag pattern flagged in #6
of sub-plan 02 — both should be fixed in the same pass.

### #3 — `get_publications_preview` re-runs the full BrowserView pipeline per preview group

(See sub-plan 02, hotspot #2.) The implementation lives in this
module:

```python
def _get_publications_preview_feed_view(self, link_spec: Link):
    feed_view = OPDS2FeedLinksView()
    feed_view.request = self.request
    group = link_spec.group
    feed_view.kwargs = {"group": group, "pks": [0], "page": 1}
    params = self.get_browser_default_params()
    if link_spec.query_params:
        for key, value in link_spec.query_params.items():
            params[snakecase(key)] = value
    params["show"].update(_PREVIEW_SHOW_PARAMS)
    params["limit"] = _PUBLICATION_PREVIEW_LIMIT

    feed_view.set_params(params)
    return feed_view

def get_publications_preview(self, link_spec: Link) -> list:
    feed_view = self._get_publications_preview_feed_view(link_spec)
    book_qs, book_count, zero_pad = feed_view.get_book_qs()
    if not book_count:
        return []

    return self.get_publications(
        book_qs,
        zero_pad,
        link_spec.title,
        items_per_page=_PUBLICATION_PREVIEW_LIMIT,
        link_spec=link_spec,
        number_of_items=book_count,
    )
```

Called from `v2/feed/groups.py:get_ordered_groups` (lines 142-150)
which iterates `PREVIEW_GROUPS`. With ~5 link specs in the default
preview group set, that's 5 separate `get_book_qs()` calls per start-
page request. Each is a full ACL + filter + annotation pipeline run.

**Severity:** medium-high on the start page, low elsewhere (preview
groups don't render on non-start pages).

### #4 — `floor(datetime.timestamp(obj.updated_at))` recomputed in `_thumb` per publication

`v2/feed/publications.py:145`:

```python
def _thumb(self, obj) -> list:
    images = []
    if not obj:
        return images
    ts = floor(datetime.timestamp(obj.updated_at))
    ...
```

Computed once per publication (`floor` of unix timestamp for the
cover URL `?ts=...` query param). The same expression appears in
`v2/manifest.py:101, 117, 137, 240, 265` — five sites total in
manifest, plus this one in publications. If a future change wants
to add `ts` to every link, the same expression needs to be
duplicated again.

Mitigation: extract a helper `_obj_ts(obj) -> int` on
`OPDS2PublicationBaseView`. Pure refactor, no perf delta on its own
(each call is ~1 µs), but reduces code duplication. Combined with a
properly-keyed cover route cache, the `?ts=` param could potentially
be dropped (tests would need to confirm the cache gets invalidated
correctly without it).

**Severity:** code health, not perf. Surface as a cleanup item.

### #5 — `_get_publications_links` builds an `HrefData` per publication that's never reused

`v2/feed/publications.py:180-187`:

```python
def _get_publications_links(self, link_spec) -> list:
    if not link_spec:
        return []
    kwargs = {"group": link_spec.group, "pks": (0,), "page": 1}
    href_data = HrefData(kwargs, link_spec.query_params, inherit_query_params=True)
    link_data = LinkData(Rel.SELF, href_data=href_data, title=link_spec.title)
    return [self.link(link_data)]
```

Called once per `get_publications` invocation, which is once per
preview group + once for the main publications section. Pure dict
construction + one `reverse()`. **Trivial,** flagged for orientation.

### #6 — `auth_link` is correctly memoized

`v2/feed/publications.py:82-93`:

```python
@property
def auth_link(self):
    if self._auth_link is None:
        ...
        self._auth_link = self.link(auth_link_data)
    return self._auth_link
```

Single computation per request, reused across every publication's
links. **No change needed** — flagged as the template for how to
handle other repeated link assemblies.

## Interactions with `BrowserView`

- `OPDS2PublicationBaseView` extends `OPDS2FeedLinksView` extends
  `OPDS2LinksView` extends `OPDSBrowserView`. All BrowserView
  pipeline machinery flows through unchanged.
- The hot loop iterates a queryset returned by `get_book_qs()`,
  which is the standard browser-views annotated/filtered queryset.
  Per-publication attribute reads (page_count, file_type, language,
  reading_direction, summary, publisher_name, imprint_name, name,
  date, updated_at, ids, pk, size) come from annotations the browser-
  views pipeline already produces.
- One peculiarity: `obj.ids` (the M2M-collected pk frozenset) is set
  by browser-views annotation only when relevant. For a Comic
  publication, `obj.ids` is `frozenset((obj.pk,))` — single-element.
  Manifest code reads `obj.ids[0]` (`v2/manifest.py:266`); make sure
  this is consistent with the annotation pipeline output.

## Open questions

- **Verify `self.admin_flags` is populated on `OPDS2PublicationBaseView`.**
  `_publication_metadata` reads it, so it must be — but trace the
  inheritance to confirm the property is reachable from this class.
- **How many preview link specs in `PREVIEW_GROUPS` actually return
  publications on a typical install?** If most are empty, the
  pipeline-rerun cost (#3) is bounded by the count check at
  `get_publications_preview` line 259 (`if not book_count: return []`).
- **Does cachalot already absorb the per-link AdminFlag query (#2)?**
  If yes, the win from converting to instance-method-and-read-from-
  cache is mostly framework-call-overhead, not DB cost.
