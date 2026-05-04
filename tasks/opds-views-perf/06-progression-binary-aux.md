# 06 — Progression, binary, and auxiliary endpoints

Smaller views that round out the OPDS surface: read-position
GET/PUT, cover/page/download binaries, the opensearch description
doc, and the authentication doc. Most are already in good shape; a
few have specific issues worth flagging.

## Files in scope

| File                                       | LOC | Purpose                                              |
| ------------------------------------------ | --- | ---------------------------------------------------- |
| `codex/views/opds/v2/progression.py`       | 229 | OPDS 2 read-position GET/PUT                         |
| `codex/views/opds/binary.py`               | 50  | Cover / custom-cover / page / download views         |
| `codex/views/opds/opensearch/v1.py`        | 20  | Static opensearch description doc                    |
| `codex/views/opds/authentication/v1.py`    | 79  | Static authentication doc                            |
| `codex/views/opds/auth.py`                 | 27  | OPDS auth helper mixin (used by binary + progression) |

## Hotspots

### #1 — `OPDS2ProgressionView.put` is a write on a read-likely-cached path

`v2/progression.py:200-229`:

```python
def put(self, *_args, **_kwargs) -> Response:
    """Update the bookmark."""
    data = self.request.data
    serializer = self.get_serializer(data=data, partial=True)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    conflict = False
    status_code = HTTPStatus.BAD_REQUEST
    if new_modified_str := data.get("modified"):
        new_modified = parse(new_modified_str)
        qs = self._get_bookmark_query()
        comic = qs.first()
        conflict = comic and comic.bookmark_updated_at > new_modified

    if conflict:
        status_code = HTTPStatus.CONFLICT
    else:
        position: int | None = (
            data.get("locator", {}).get("locations", {}).get("position")
        )
        if position is not None:
            page = max(position - 1, 0)
            self.kwargs["page"] = page
            max(position - 1, 0)  # ← dead expression, line 226
            self.update_bookmark()
            status_code = HTTPStatus.OK
    return Response(status=status_code)
```

Two findings:

- **Dead expression at line 226** (`max(position - 1, 0)` with no
  assignment). Pure code-health bug, not perf — surface in
  cross-cutting cleanup.
- **Conflict check fires `_get_bookmark_query()` and `qs.first()`
  before doing the actual bookmark write.** That's two queries on
  every PUT (the conflict check + the write itself). Common case
  (no conflict, fresh write) pays for the conflict check
  unnecessarily. This is correctness-driven per the OPDS spec — but
  the conflict check could be folded into the same `update_bookmark`
  call by checking the row's `updated_at` in the WHERE clause of the
  UPDATE.
- **`self.update_bookmark()` flushes cachalot rows for `Bookmark`.**
  Same pattern flagged in browser-views perf #8 — bookmark writes
  invalidate cachalot. For OPDS this fires every time a reader app
  syncs progression, so on a high-throughput install with many
  active readers, the cachalot churn is real.

Mitigation:

- **Drop the conflict pre-check.** Use a conditional UPDATE:
  `Bookmark.objects.filter(pk=..., updated_at__lte=new_modified)
  .update(...)` and check the row count to detect conflict. Single
  query.
- **Tag `update_bookmark` writes with cachalot-skip.** cachalot
  supports per-table skipping; bookmark progression updates are
  high-frequency and don't benefit from cachalot caching anyway.

**Severity:** medium. Aggregate cost depends on PUT volume; OPDS
clients sync progression on every page turn for some apps.

### #2 — `OPDS2ProgressionView.get` runs the full ACL filter for one comic

`v2/progression.py:135-156`:

```python
def _get_bookmark_query(self) -> QuerySet:
    group = self.kwargs.get("group")
    pk = self.kwargs.get("pk")
    ...
    model = GROUP_MODEL_MAP.get(group)
    ...
    acl_filter = self.get_acl_filter(model, self.request.user)
    qs = model.objects.filter(acl_filter).distinct()

    bm_rel = self.get_bm_rel(model)
    bm_filter = self.get_my_bookmark_filter(bm_rel)
    return qs.annotate(
        my_bookmark=FilteredRelation("bookmark", condition=bm_filter),
        bookmark_updated_at=F("my_bookmark__updated_at"),
    )
```

For a single-comic GET, this builds a queryset that includes the
full ACL filter (visible-libraries subquery) + `FilteredRelation`
annotation. Then `qs.get(pk=pk)` (line 174) materializes one row.

The ACL filter is necessary (correctly refuses to leak progression
for invisible comics). The cost is in the ACL filter's underlying
visible-libraries computation, which the browser plan's
`GroupACLMixin._cached_visible_library_pks` already memoizes
per-request. So this is mostly fine.

**Severity:** low. Flagged for completeness.

### #3 — `OPDS2ProgressionView` re-runs `_get_bookmark_query` twice in PUT

`put()` calls `_get_bookmark_query()` (line 211) for the conflict
check, then `update_bookmark()` (line 227) presumably also does its
own bookmark fetch. **Two `_get_bookmark_query` builds + two ACL
filter computations per PUT** unless `update_bookmark` shares state.

Mitigation:

- See #1 — folding into one conditional UPDATE eliminates this.
- Alternatively, memoize the bookmark queryset on the view instance
  (cheap; per-request).

**Severity:** low-medium. Tied to #1; same fix.

### #4 — Binary endpoints inherit cover/download views from browser

`codex/views/opds/binary.py:1-50` defines `OPDSCoverView`,
`OPDSCustomCoverView`, `OPDSPageView`, `OPDSDownloadView` — all are
thin subclasses of the corresponding browser views with
`OPDSAuthMixin` applied for OPDS auth (Basic / Bearer / Session).

Browser-views perf Stage 3 + Stage 5a already cover the cover
endpoint cost (correlated-subquery `cover_pk` + `cache_page` on the
per-pk route). The OPDS routes use the same per-pk endpoint, so
they inherit the wins.

**No change needed.** Cover route caching is already correct here.

### #5 — Opensearch and authentication doc views are static

`codex/views/opds/opensearch/v1.py` (20 LOC) renders a fixed XML
template. `codex/views/opds/authentication/v1.py` (79 LOC) builds a
JSON auth doc with server URLs. Both are user-agnostic.

When `OPDS_TIMEOUT` is set (sub-plan 01 #1), these are the cheapest
wins of all — pure-static responses currently rendered per request.

**Severity:** trivial individually. Wins flow from #1 in sub-plan 01.

### #6 — `OPDSAuthMixin` re-validates auth on every binary request

`codex/views/opds/auth.py:1-27` adds `OPDSAuthMixin` to every binary
view. The mixin runs DRF's authentication classes — Basic + Bearer +
Session. Per-request auth validation is unavoidable (it's how DRF
works) but worth noting that **every cover GET pays a Basic-auth
hash comparison + DB user lookup** if the client uses Basic auth
(which OPDS clients commonly do).

Mitigation: out of scope for this plan. Auth caching belongs in a
broader auth perf project. Flagged for awareness.

**Severity:** medium aggregate (every cover hit pays this), but not
fixable here.

## Interactions with `BrowserView`

- `OPDS2ProgressionView` does **not** extend `BrowserView`. It builds
  its own minimal queryset via `_get_bookmark_query()`. Most of the
  browser-views annotation pipeline is bypassed — by design, since
  progression doesn't need any of it.
- Binary views inherit from the corresponding browser views, so all
  cover/page/download wins flow through.

## Open questions

- **How often do clients PUT progression?** Determines whether the
  cachalot-flush impact (#1) is a real concern or background noise.
- **Does `update_bookmark()` in `BookmarkPageMixin` already do
  conditional UPDATE?** If yes, the PUT pre-check is purely
  redundant. If no, replacing it is the elegant fix.
- **Could the opensearch description doc be served as a Django
  static file?** It's truly static (no per-server URLs that aren't
  build-time-resolvable). Pulling it out of the view layer would
  bypass DRF entirely. Worth investigating, but may not be worth
  the complexity.
