# Favorites — Handoff

Pick this up alongside `00-plan.md` for the design context. Backend is
done end-to-end; everything left is frontend (plus a small README/smoke
wrap-up).

## Where things stand

**Backend phases 1–6 of 9 landed and committed on
`claude/brave-cori-4c2730`.**

```
4eec4158 surface a Favorites preview on the OPDS v2 start page
280c9687 add favorite as editable table-view column
4fef7e35 add favorites-only filter to browser pipeline
5adb70e6 add favorites HTTP API at /api/v3/favorites/
caad3852 cascade favorites on target-row delete via signals + nightly sweep
81ba23f7 add Favorite model + migration for per-user favorites
```

**212/212 backend tests pass.** ruff, basedpyright, vulture, complexipy,
codespell are clean on every touched file. `make lint` exits non-zero
because of a pre-existing remark markdown failure (worktree contains
`.claude`) — verified to reproduce on the clean tree, not introduced
by this work. Confirmed with the user to ignore.

## What works end-to-end without any frontend changes

A user can drive the whole feature today via curl:

```sh
# Favorite a series.
curl -X PUT $URL/api/v3/favorites/s/42/

# Toggle off.
curl -X DELETE $URL/api/v3/favorites/s/42/

# Hydrate per-group sets.
curl $URL/api/v3/favorites/
# → {"p":[],"i":[],"s":[42],"v":[],"f":[],"a":[],"c":[]}

# Filter the browser to favorites-only.
curl -X PATCH $URL/api/v3/r/settings \
  -H 'Content-Type: application/json' \
  -d '{"filters":{"favorite": true}}'
```

The favorite column shows up in the table view's column picker as
`favorite` with a checkbox edit widget; clicking the header sorts by
`favorite` (`is_favorite` annotation, `favorite` order_by enum). OPDS
v2's start page shows a "Favorites" preview tile when (and only when)
`Favorite.objects.filter(user=request.user).exists()`.

## Key contracts the frontend will consume

### REST endpoints

| Method | Path | Body | Status | Purpose |
|---|---|---|---|---|
| `PUT` | `/api/v3/favorites/<group>/<int:target_id>/` | none | 201 created / 200 already exists / 404 unknown or hidden / 400 unmapped group / 403 anonymous | Idempotent toggle on |
| `DELETE` | `/api/v3/favorites/<group>/<int:target_id>/` | none | 204 always (idempotent) / 400 unmapped group / 403 anonymous | Idempotent toggle off |
| `GET` | `/api/v3/favorites/` | — | 200 → `{"p":[…],"i":[…],"s":[…],"v":[…],"f":[…],"a":[…],"c":[…]}` | Hydrate per-group Sets |

`<group>` is the existing single-letter URL converter (regex
`[rpisvcfa]`) — `r` parses but the view returns 400 since root isn't
favorite-able.

### Browser settings filter

`PATCH /api/v3/r/settings` accepts `{"filters":{"favorite": <bool>}}`.
Default is `false`. The favorite filter composes with the bookmark
filter in the existing `Q()` chain.

### Table column

The column key in `BROWSER_TABLE_COLUMNS` is `favorite`. It's the
**first `editable: True` entry in the registry** — the existing
"only-`favorite`-is-editable" invariant test in
`tests/test_browser_columns_registry.py` enforces this.

`edit_widget` is `"checkbox"` for now. The frontend will probably want
a dedicated star widget — Phase 8 territory. Keep the model edit by
re-using the existing `PUT/DELETE` endpoints; nothing new to wire in
the column-edit pipeline.

The `favorite` annotation alias on the queryset is just `favorite`
(no prefix). For authenticated users on a favorite-able model it's an
`Exists(Favorite.objects.filter(user, group, target_id=OuterRef("pk")))`;
for anonymous sessions it's a `Value(False)` constant. Always-on in
table view (cheap per-row Exists, removes sort gating). Sort key in
`BROWSER_ORDER_BY_CHOICES` is also `favorite`.

### OPDS

`?filters={"favorite": true}` already works on every OPDS v2 feed —
the filter serializer is shared with the browser. The OPDS v2 start
page conditionally surfaces a Favorites tile via
`OPDS2FeedGroupsView.get_ordered_groups`. OPDS v1 was deferred —
modern clients use v2 and the v1 facet structure is separate.

## What's left

### Phase 7 — Frontend store + API client

- `frontend/src/api/v3/favorites.js` — xior client for `PUT|DELETE|GET
  /api/v3/favorites/...`. Match the existing `api/v3/*.js` style
  (the `browser.js` and reader-store examples are the closest pattern).
- `frontend/src/stores/favorites.js` — Pinia store with state
  `favoriteIds: { p: Set, i: Set, s: Set, v: Set, f: Set, a: Set,
  c: Set }`, action `hydrate()` (called on auth), action
  `toggle(group, pk)` with optimistic update + rollback on error,
  getter `isFavorite(group, pk)`.
- Wire hydration into the existing auth flow on login so the store
  is warm when the toolbar / cards render.
- vitest unit tests for the toggle path, optimistic rollback, hydrate.

### Phase 8 — Frontend UI

- Star toggle component (probably
  `frontend/src/components/common/FavoriteToggle.vue`) — props
  `group`, `pk`. Reads from `favorites` store, calls `toggle`. Reused
  in three mount sites:
  - browser cards (`components/browser/`)
  - reader header (`components/reader/`)
  - the `favorite` table column cell (extend
    `components/browser/table/browser-table-cell.vue` or wire a
    column-specific renderer — the table-view feature already has a
    cell-renderer pattern)
- Browser toolbar settings panel: add a "favorites only" toggle that
  writes `filters.favorite` into the `browser` Pinia store. The
  `bookmark` filter UI is a sibling to mirror.
- Column picker should already display `favorite` from the
  regenerated `frontend/src/choices/browser-table-columns.json` —
  worth confirming the picker doesn't blow up on the first
  `editable: True` entry, since up until this PR the registry
  guaranteed `editable=False` for everything.

### Phase 9 — Integration smoke + docs

- End-to-end manual smoke: favorite items at every group level →
  confirm filter, table column, OPDS preview tile, signal cleanup on
  delete.
- README features section: add a "Favorites" bullet alongside the
  table-view bullet that the prior PR added.
- Optional: a tighter OPDS feed test (`tests/test_favorites_opds.py`?)
  hitting the v2 start endpoint and asserting on the preview tile's
  presence/absence based on `Favorite` table state. Deferred from
  Phase 6.

## Decisions made along the way (worth flagging)

1. **Per-user, authenticated only.** Confirmed with the user before
   Phase 1 — bookmarks need anonymous-session support for in-flight
   reading state, but favorites are persistent intent and don't.
   `permission_classes = (IsAuthenticated,)` on every view; PUT/DELETE
   from anonymous sessions return 403 (DRF default for `IsAuthenticated`).
2. **404 on PUT for hidden targets** (rather than 403). The view runs
   `get_acl_filter(model, user)` and reports 404 when the target row
   exists but the user can't see it, so an attacker can't probe the
   existence of restricted rows.
3. **Group-letter keying (`p|i|s|v|f|a|c`) over GenericForeignKey or
   per-group through-tables.** Discussed up front in the design
   conversation; user confirmed "single favorite table." See the
   commit message on `81ba23f7` for the perf reasoning.
4. **Table-column annotation always-on in table view** (not gated on
   "favorite is in the column set"). The per-row `Exists` is one
   indexed scan; gating means the order-by enum'd reject `favorite`
   when the column wasn't picked, which would surprise the user.
5. **The existing `test_editable_is_false_in_v1` invariant got tightened
   to `test_only_favorite_is_editable`.** This is a real semantic
   change — if a future feature flips a second column to editable,
   that test fails until updated. Intentional.
6. **OPDS v1 is deferred.** v2 is the modern surface; v1 has a
   separate facet structure (`RootTopLinks`, `FacetGroup` /
   `Facet`). If a v1 client needs the surface it's a small follow-up
   mirroring v2's `FAVORITES_PREVIEW_GROUP` shape.
7. **`_save_browser_filters` got a small refactor**: the inline
   `value if key == "bookmark" else (list(value) if value else [])`
   conditional grew an explicit branch for `favorite` (boolean) so
   the truthy/falsy coercion doesn't corrupt the field. This is the
   only place outside Phase 4's direct files where I touched
   pre-existing code; the change is local and behavior-preserving for
   bookmark.

## Open questions for the next session

None blocking. The frontend phases are well-specified by the plan and
the contracts above. If something feels under-specified once you're
in Vue land, the codebase has a strong "look at the bookmark/sibling"
analog for almost every favorite mechanic.

## Quick verification commands

```sh
# Backend (should be green).
LOGLEVEL=WARNING uv run --group test pytest --no-cov --ignore=tests/perf -q

# Lint the changed surface.
uv run --group lint ruff check codex/ tests/
uv run --group lint --group test --group build basedpyright codex/views/favorites.py codex/views/browser/columns.py codex/views/browser/filters/filter.py
uv run --group lint complexipy codex/views/favorites.py codex/views/browser/columns.py
```

## Files touched

### Phase 1 (model)
- `codex/models/favorite.py` — new
- `codex/migrations/0043_favorite.py` — new
- `codex/models/__init__.py` — wildcard import
- `tests/test_models.py` — `FavoriteTestCase`

### Phase 2 (signals + cron)
- `codex/signals/django_signals.py` — `_on_favorite_target_deleted`
- `codex/librarian/scribe/janitor/cleanup.py` — `cleanup_orphan_favorites`
- `codex/librarian/scribe/janitor/janitor.py` — register task in 3 maps
- `codex/librarian/scribe/janitor/status.py` — `JanitorCleanupFavoritesStatus`
- `codex/librarian/scribe/janitor/tasks.py` — `JanitorCleanupFavoritesTask`
- `tests/test_models.py` — `test_target_delete_cascades_via_signal`

### Phase 3 (API)
- `codex/views/favorites.py` — new
- `codex/urls/api/favorites.py` — new
- `codex/urls/api/v3.py` — mount the routes
- `tests/test_favorites_api.py` — new (8 tests)

### Phase 4 (browser filter)
- `codex/models/settings.py` — `favorite` field on `SettingsBrowserFilters`
- `codex/migrations/0044_settingsbrowserfilters_favorite_and_more.py` — new
- `codex/serializers/browser/filters.py` — `favorite` boolean
- `codex/views/browser/filters/filter.py` — `get_favorite_filter`
- `codex/views/settings.py` — scalar branch in `_save_browser_filters`
- `tests/test_favorites_api.py` — `FavoriteFilterTestCase`

### Phase 5 (table column)
- `codex/choices/browser.py` — `favorite` in registry + order_by
- `codex/views/browser/columns.py` — `favorite_annotation_for`
- `codex/views/browser/browser.py` — `_add_table_view_favorite_annotation`
- `codex/migrations/0045_alter_settingsbrowser_order_by.py` — new
- `tests/test_browser_columns_registry.py` — invariant tightened
- `tests/test_favorites_api.py` — `FavoriteAnnotationTestCase`

### Phase 6 (OPDS)
- `codex/views/opds/const.py` — `FavoriteFilters`
- `codex/views/opds/v2/const.py` — `FAVORITES_PREVIEW_GROUP`
- `codex/views/opds/v2/feed/groups.py` — `_user_has_favorites` + conditional include
